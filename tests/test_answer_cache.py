"""Tests for VQ-210: Tenant-scoped answer cache."""

import hashlib
import pytest
import pytest_asyncio
from uuid import UUID, uuid4
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.answer_cache import AnswerCache
from app.models.document import Document
from app.models.tenant import Tenant
from app.models.user import User
from app.services.answer_cache import AnswerCacheService
from app.auth.password import hash_password


@pytest.fixture
def sample_question():
    return "What is the refund policy?"


@pytest.fixture
def sample_question_hash(sample_question):
    return hashlib.sha256(sample_question.strip().lower().encode("utf-8")).hexdigest()


@pytest_asyncio.fixture
async def tenant_a(db_session: AsyncSession):
    """Create tenant A with a client admin."""
    tenant = Tenant(
        short_code="TENANT_A",
        name="Tenant A",
        status="active",
        storage_quota_mb=2048,
        knowledge_base_version=0,
    )
    db_session.add(tenant)
    await db_session.flush()

    # Create a user for the tenant
    user = User(
        tenant_id=tenant.id,
        email="admin@tenant-a.com",
        password_hash=hash_password("StrongPass1!"),
        role="client_admin",
    )
    db_session.add(user)
    await db_session.flush()

    return tenant


@pytest_asyncio.fixture
async def tenant_b(db_session: AsyncSession):
    """Create tenant B with a client admin."""
    tenant = Tenant(
        short_code="TENANT_B",
        name="Tenant B",
        status="active",
        storage_quota_mb=2048,
        knowledge_base_version=0,
    )
    db_session.add(tenant)
    await db_session.flush()

    user = User(
        tenant_id=tenant.id,
        email="admin@tenant-b.com",
        password_hash=hash_password("StrongPass1!"),
        role="client_admin",
    )
    db_session.add(user)
    await db_session.flush()

    return tenant


@pytest_asyncio.fixture
async def user_a(db_session: AsyncSession, tenant_a: Tenant):
    """Get the user for tenant A."""
    from sqlalchemy import select
    result = await db_session.execute(
        select(User).where(User.tenant_id == tenant_a.id)
    )
    return result.scalar_one()


@pytest_asyncio.fixture
async def user_b(db_session: AsyncSession, tenant_b: Tenant):
    """Get the user for tenant B."""
    from sqlalchemy import select
    result = await db_session.execute(
        select(User).where(User.tenant_id == tenant_b.id)
    )
    return result.scalar_one()


@pytest_asyncio.fixture
async def document_a(db_session: AsyncSession, tenant_a: Tenant, user_a: User):
    """Create a document for tenant A."""
    doc = Document(
        tenant_id=tenant_a.id,
        original_filename="policy.pdf",
        stored_filename="policy.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        uploaded_by=user_a.id,
    )
    db_session.add(doc)
    await db_session.flush()
    return doc


@pytest_asyncio.fixture
async def document_b(db_session: AsyncSession, tenant_b: Tenant, user_b: User):
    """Create a document for tenant B."""
    doc = Document(
        tenant_id=tenant_b.id,
        original_filename="policy.pdf",
        stored_filename="policy.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        uploaded_by=uuid4(),
    )
    db_session.add(doc)
    await db_session.flush()
    return doc


class TestAnswerCache:
    """Tests for the AnswerCacheService."""

    async def test_same_tenant_same_role_hits_cache(
        self, db_session: AsyncSession, tenant_a: Tenant, document_a: Document
    ):
        """Same tenant, role, question, kb_version -> cache hit."""
        question = "What is the refund policy?"
        role = "employee"
        kb_version = 1

        # First request - miss
        entry1 = await AnswerCacheService.set(
            db_session,
            tenant_id=tenant_a.id,
            role=role,
            question="What is the refund policy?",
            kb_version=kb_version,
            answer_text="Refunds are processed within 30 days.",
            source_document_id=document_a.id,
            source_chunk_id=uuid4(),
        )
        await db_session.commit()

        # Second request - hit
        cached = await AnswerCacheService.get(
            db_session,
            tenant_id=tenant_a.id,
            role="employee",
            question="What is the refund policy?",
            kb_version=kb_version,
        )
        assert cached is not None
        assert cached.id == entry1.id
        assert cached.answer_text == "Refunds are processed within 30 days."

    async def test_different_tenant_misses_cache(
        self, db_session: AsyncSession, tenant_a: Tenant, tenant_b: Tenant, document_a: Document
    ):
        """Tenant B asking same question -> cache miss."""
        question = "What is the refund policy?"
        role = "employee"
        kb_version = 1

        # Tenant A caches answer
        await AnswerCacheService.set(
            db_session,
            tenant_id=tenant_a.id,
            role=role,
            question="What is the refund policy?",
            kb_version=kb_version,
            answer_text="Refunds are processed within 30 days.",
            source_document_id=document_a.id,
            source_chunk_id=uuid4(),
        )
        await db_session.commit()

        # Tenant B asks same question
        cached = await AnswerCacheService.get(
            db_session,
            tenant_id=tenant_b.id,
            role=role,
            question="What is the refund policy?",
            kb_version=kb_version,
        )
        assert cached is None

    async def test_different_role_misses_cache(
        self, db_session: AsyncSession, tenant_a: Tenant, document_a: Document
    ):
        """Same tenant, different role -> cache miss."""
        question = "What is the refund policy?"
        kb_version = 1

        # Employee caches
        await AnswerCacheService.set(
            db_session,
            tenant_id=tenant_a.id,
            role="employee",
            question=question,
            kb_version=1,
            answer_text="Refunds within 30 days.",
            source_document_id=document_a.id,
            source_chunk_id=uuid4(),
        )
        await db_session.commit()

        # Client admin asks same question
        cached = await AnswerCacheService.get(
            db_session,
            tenant_id=tenant_a.id,
            role="client_admin",
            question=question,
            kb_version=kb_version,
        )
        assert cached is None

    async def test_kb_version_bump_invalidates(
        self, db_session: AsyncSession, tenant_a: Tenant, document_a: Document
    ):
        """KB version bump invalidates cache."""
        question = "What is the refund policy?"
        role = "employee"

        # Cache at version 1
        await AnswerCacheService.set(
            db_session,
            tenant_id=tenant_a.id,
            role=role,
            question=question,
            kb_version=1,
            answer_text="Old answer.",
            source_document_id=document_a.id,
            source_chunk_id=uuid4(),
        )
        await db_session.commit()

        # Verify hit at version 1
        cached = await AnswerCacheService.get(db_session, tenant_a.id, role, question, 1)
        assert cached is not None
        assert cached.answer_text == "Old answer."

        # Version bump to 2
        cached = await AnswerCacheService.get(db_session, tenant_a.id, role, question, 2)
        assert cached is None

    async def test_question_normalization(
        self, db_session: AsyncSession, tenant_a: Tenant, document_a: Document
    ):
        """Question normalization: case/whitespace differences hit same cache."""
        kb_version = 1

        # First with "What is X?"
        await AnswerCacheService.set(
            db_session,
            tenant_id=tenant_a.id,
            role="employee",
            question="What is the refund policy?",
            kb_version=1,
            answer_text="Answer 1.",
            source_document_id=document_a.id,
            source_chunk_id=uuid4(),
        )
        await db_session.commit()

        # Query with different case/whitespace
        cached = await AnswerCacheService.get(
            db_session,
            tenant_id=tenant_a.id,
            role="employee",
            question="  what is the refund policy?  ",
            kb_version=1,
        )
        assert cached is not None
        assert cached.answer_text == "Answer 1."

    async def test_rls_enforcement(
        self, app_db_session: AsyncSession
    ):
        """RLS prevents cross-tenant access at database level."""
        import psycopg2
        import uuid
        from app.config import get_settings
        settings = get_settings()

        def get_admin_connection():
            return psycopg2.connect(settings.DATABASE_URL_SYNC)

        # Setup: create two tenants, a document, and a cache entry using admin connection
        conn = get_admin_connection()
        cur = conn.cursor()
        cur.execute("TRUNCATE answer_cache, documents, users, tenants CASCADE")
        conn.commit()

        cur.execute("INSERT INTO tenants (short_code, name, status, storage_quota_mb, knowledge_base_version) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    ("TENANT_A", "Tenant A", "active", 2048, 1))
        tenant_a_id = cur.fetchone()[0]

        cur.execute("INSERT INTO tenants (short_code, name, status, storage_quota_mb, knowledge_base_version) VALUES (%s, %s, %s, %s, %s) RETURNING id",
                    ("TENANT_B", "Tenant B", "active", 2048, 1))
        tenant_b_id = cur.fetchone()[0]

        user_a_id = uuid.uuid4()
        cur.execute(
            "INSERT INTO users (id, tenant_id, email, password_hash, role) VALUES (%s, %s, %s, %s, %s)",
            (str(user_a_id), str(tenant_a_id), "admin@tenant-a.com", "hash", "client_admin")
        )

        doc_a_id = uuid.uuid4()
        cur.execute(
            "INSERT INTO documents (id, tenant_id, original_filename, stored_filename, mime_type, size_bytes, uploaded_by) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (str(doc_a_id), str(tenant_a_id), "policy.pdf", "policy.pdf", "application/pdf", 1024, str(user_a_id))
        )

        # Insert cache entry for tenant A
        chunk_id = uuid.uuid4()
        cur.execute(
            """INSERT INTO answer_cache (tenant_id, role, question_hash, kb_version, answer_text, source_document_id, source_chunk_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (str(tenant_a_id), "employee", "a" * 64, 1, "Answer A", str(doc_a_id), str(chunk_id))
        )
        entry_a_id = cur.fetchone()[0]

        conn.commit()
        cur.close()
        conn.close()

        # Now test with app_db_session (vaultiq_app role - NOBYPASSRLS)
        # Set context to tenant_b - should NOT see tenant_a's cache entry
        from app.database import set_tenant_context
        await set_tenant_context(app_db_session, str(tenant_b_id))

        result = await app_db_session.execute(
            text("SELECT * FROM answer_cache WHERE id = :eid"), {"eid": str(entry_a_id)}
        )
        assert result.scalar_one_or_none() is None

        # Set context to tenant_a - SHOULD see tenant_a's cache entry
        await set_tenant_context(app_db_session, str(tenant_a_id))

        result = await app_db_session.execute(
            text("SELECT * FROM answer_cache WHERE id = :eid"), {"eid": str(entry_a_id)}
        )
        assert result.scalar_one_or_none() is not None

    async def test_invalidate_tenant(
        self, db_session: AsyncSession, tenant_a: Tenant, document_a: Document
    ):
        """invalidate_tenant removes all entries for a tenant."""
        # Add multiple entries
        for i in range(3):
            await AnswerCacheService.set(
                db_session,
                tenant_id=tenant_a.id,
                role="employee",
                question=f"Question {i}",
                kb_version=1,
                answer_text=f"Answer {i}",
                source_document_id=document_a.id,
                source_chunk_id=uuid4(),
            )
        await db_session.commit()

        # Invalidate
        count = await AnswerCacheService.invalidate_tenant(db_session, tenant_a.id)
        await db_session.commit()

        assert count == 3

        # Verify all gone
        from sqlalchemy import select
        result = await db_session.execute(
            select(AnswerCache).where(AnswerCache.tenant_id == tenant_a.id)
        )
        assert result.scalars().all() == []

    async def test_unique_constraint(
        self, db_session: AsyncSession, tenant_a: Tenant, document_a: Document
    ):
        """Unique constraint prevents duplicate cache entries."""
        chunk_id = uuid4()
        await AnswerCacheService.set(
            db_session,
            tenant_id=tenant_a.id,
            role="employee",
            question="What is the refund policy?",
            kb_version=1,
            answer_text="Answer 1.",
            source_document_id=document_a.id,
            source_chunk_id=chunk_id,
        )
        await db_session.commit()

        # Second insert with same key should fail
        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            await AnswerCacheService.set(
                db_session,
                tenant_id=tenant_a.id,
                role="employee",
                question="What is the refund policy?",
                kb_version=1,
                answer_text="Answer 2.",
                source_document_id=document_a.id,
                source_chunk_id=chunk_id,
            )
            await db_session.commit()

    async def test_kb_version_from_tenant(
        self, db_session: AsyncSession, tenant_a: Tenant
    ):
        """get_kb_version returns correct version."""
        # Default is 0
        version = await AnswerCacheService.get_kb_version(db_session, tenant_a.id)
        assert version == 0

        # Set to 5
        tenant_a.knowledge_base_version = 5
        await db_session.commit()

        version = await AnswerCacheService.get_kb_version(db_session, tenant_a.id)
        assert version == 5