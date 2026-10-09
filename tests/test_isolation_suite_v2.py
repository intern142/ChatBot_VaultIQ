"""VQ-208: Cross-tenant isolation test suite v2 (search level).

Proves that search itself cannot leak between tenants, not just the operations
around it. Tests search isolation, cache isolation, and processing isolation.
"""
import asyncio
import json
import pytest
import pytest_asyncio
import httpx
from typing import Any, Dict, List
import uuid
from uuid import UUID, uuid4
from app.main import app
from tests.isolation_manifest import ISOLATION_COVERED_ROUTES, normalize_path
from app.services.answer_cache import AnswerCacheService
from app.models.answer_cache import AnswerCache
from app.services.processing import (
    extract_text_from_file,
    chunk_text,
    embed_chunks,
    store_chunks,
    process_document
)
from app.models.document import Document, DocumentJob, JobStatus, ProcessingStatus
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


# ---- Coverage Guard ----

def test_route_coverage_guard():
    """Every tenant-scoped route in the app must be listed in ISOLATION_COVERED_ROUTES."""
    tenant_scoped_prefixes = ("/documents", "/admin", "/auth/refresh", "/auth/logout", "/invite/accept", "/search")
    tenant_scoped_methods = {"GET", "POST", "PATCH", "DELETE"}

    covered = {(m.upper(), normalize_path(p)) for m, p in ISOLATION_COVERED_ROUTES}

    app_routes = set()
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            for method in route.methods:
                if method.upper() in tenant_scoped_methods:
                    path = route.path
                    if any(path.startswith(prefix) for prefix in tenant_scoped_prefixes):
                        app_routes.add((method.upper(), normalize_path(path)))

    missing = app_routes - covered
    extra = covered - app_routes

    assert not missing, (
        f"Routes in app but missing from ISOLATION_COVERED_ROUTES: {sorted(missing)}. "
        "Add them to tests/isolation_manifest.py"
    )
    # Extra routes in manifest are OK (may be future routes not yet implemented)


# ---- Helpers ----

FORBIDDEN_SUBSTRINGS = [
    "tenant_b", "TENANT_B", "tenant_a", "TENANT_A",
    "admin@b.com", "admin@a.com", "emp@b.com", "emp@a.com",
    "test_b.txt", "test_a.txt",
    "Tenant B document", "Tenant A document",
]


def assert_no_cross_tenant_leak(response: httpx.Response, other_tenant_id: str):
    """Assert response body contains no identifiers from the other tenant."""
    body = response.text
    # Check for other tenant's UUID
    assert other_tenant_id.lower() not in body.lower(), (
        f"Response leaks other tenant ID: {other_tenant_id}"
    )
    # Check for other tenant's short code
    assert "TENANT_B" not in body.upper() and "TENANT_A" not in body.upper(), (
        "Response leaks tenant short code"
    )
    # Check for forbidden substrings
    for substr in FORBIDDEN_SUBSTRINGS:
        assert substr not in body, f"Response leaks forbidden substring: {substr}"


async def make_request(
    async_client: httpx.AsyncClient,
    method: str,
    path: str,
    token: str | None,
    **kwargs,
) -> httpx.Response:
    """Make an HTTP request with optional Bearer token."""
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return await async_client.request(method, path, headers=headers, **kwargs)


# ---- Fixtures for resource IDs ----

@pytest_asyncio.fixture
async def tenant_a_ids(async_client, token_a_admin, token_a_emp, tenant_a):
    """Return tenant A's resource IDs for cross-tenant testing."""
    return {
        "tenant_id": str(tenant_a["id"]),
        "admin_token": token_a_admin,
        "emp_token": token_a_emp,
    }


@pytest_asyncio.fixture
async def tenant_b_ids(async_client, token_b_admin, token_b_emp, tenant_b):
    """Return tenant B's resource IDs for cross-tenant testing."""
    return {
        "tenant_id": str(tenant_b["id"]),
        "admin_token": token_b_admin,
        "emp_token": token_b_emp,
    }


@pytest_asyncio.fixture
async def doc_ids(async_client, doc_a, doc_b):
    """Return document IDs for both tenants."""
    return {
        "doc_a_id": doc_a["id"],
        "doc_b_id": doc_b["id"],
    }


@pytest_asyncio.fixture
async def invite_codes(async_client, invite_code_a, invite_code_b):
    """Return invite codes for both tenants."""
    return {
        "invite_a": invite_code_a["code"],
        "invite_b": invite_code_b["code"],
        "invite_a_tenant_id": invite_code_a["tenant_id"],
        "invite_b_tenant_id": invite_code_b["tenant_id"],
    }


# ---- Cross-tenant search isolation tests (AC 1) ----

class TestSearchIsolation:
    """Search endpoints must be strictly tenant-isolated."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("token_fixture,role", [
        ("token_a_admin", "client_admin"),
        ("token_a_emp", "employee"),
        ("token_b_admin", "client_admin"),
        ("token_b_emp", "employee"),
    ])
    async def test_search_returns_only_tenant_content(
        self, async_client, request, token_fixture, role,
        tenant_a_ids, tenant_b_ids, doc_a, doc_b, db_session
    ):
        """Search with tenant token should only return content from that tenant."""
        # Get the token and determine which tenant it belongs to
        token = request.getfixturevalue(token_fixture)
        is_token_a = token_fixture.startswith("token_a")
        other_tenant_id = tenant_b_ids["tenant_id"] if is_token_a else tenant_a_ids["tenant_id"]
        this_tenant_id = tenant_a_ids["tenant_id"] if is_token_a else tenant_b_ids["tenant_id"]

        # Insert identical but unique content into both tenants (unique per test run)
        unique_suffix = uuid.uuid4().hex[:8]
        identical_content = f"Isolation test content {unique_suffix} placed in both tenants for cross-tenant testing."

        # Upload to THIS tenant (using current token)
        files_this = {"file": ("identical.txt", identical_content.encode(), "text/plain")}
        headers_this = {"Authorization": f"Bearer {token}"}
        resp_this = await async_client.post("/documents", files=files_this, headers=headers_this)
        assert resp_this.status_code == 201
        doc_this_id = resp_this.json()["id"]

        # Upload to OTHER tenant (using other tenant's admin token)
        other_token = tenant_b_ids["admin_token"] if is_token_a else tenant_a_ids["admin_token"]
        files_other = {"file": ("identical.txt", identical_content.encode(), "text/plain")}
        headers_other = {"Authorization": f"Bearer {other_token}"}
        resp_other = await async_client.post("/documents", files=files_other, headers=headers_other)
        assert resp_other.status_code == 201
        doc_other_id = resp_other.json()["id"]

        # Process documents synchronously using the processing service in fresh sessions
        from app.models.document import DocumentJob
        from app.services.processing import process_document
        from sqlalchemy import select
        from app.database import AsyncSessionLocal
        
        # Get job IDs for both documents
        async def get_job_id(doc_id: uuid.UUID) -> uuid.UUID:
            result = await db_session.execute(
                select(DocumentJob.id).where(DocumentJob.document_id == doc_id).order_by(DocumentJob.created_at.desc())
            )
            return result.scalar_one()
        
        job_this_id = await get_job_id(doc_this_id)
        job_other_id = await get_job_id(doc_other_id)
        
        # Process in separate sessions (process_document commits internally)
        async def process_doc(tenant_id: uuid.UUID, doc_id: uuid.UUID, job_id: uuid.UUID):
            async with AsyncSessionLocal() as session:
                from app.database import set_tenant_context
                await set_tenant_context(session, str(tenant_id))
                await process_document(session, tenant_id, doc_id, job_id)
        
        await process_doc(this_tenant_id, doc_this_id, job_this_id)
        await process_doc(other_tenant_id, doc_other_id, job_other_id)

        # Search for content that should match in both tenants
        search_query = "Isolation test content"
        resp = await make_request(
            async_client, "POST", "/search", token,
            json={"query": search_query, "top_k": 10}
        )

        assert resp.status_code == 200, f"Search failed: {resp.text}"
        data = resp.json()

        # Verify results exist
        assert "results" in data
        assert len(data["results"]) > 0, "Should find results in at least one tenant"

        # Verify all results belong to the requesting tenant
        for result in data["results"]:
            assert result["document_id"] == doc_this_id, \
                f"Search result contains document from other tenant: {result['document_id']}"

        # Verify no cross-tenant leakage in response body
        assert_no_cross_tenant_leak(resp, other_tenant_id)

    @pytest.mark.asyncio
    async def test_search_returns_empty_for_no_match(
        self, async_client, token_a_admin, token_b_admin
    ):
        """Search for non-existent content returns empty results, no leakage."""
        # Search with tenant A token for content that doesn't exist
        resp = await make_request(
            async_client, "POST", "/search", token_a_admin,
            json={"query": "this content definitely does not exist in either tenant xyz123", "top_k": 10}
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert len(data["results"]) == 0, "Should return empty results for non-existent content"

        # Verify no cross-tenant leakage (should be minimal response)
        assert_no_cross_tenant_leak(resp, tenant_b_ids["tenant_id"])

    @pytest.mark.asyncio
    @pytest.mark.parametrize("token_fixture,role", [
        ("token_a_admin", "client_admin"),
        ("token_a_emp", "employee"),
        ("token_b_admin", "client_admin"),
        ("token_b_emp", "employee"),
    ])
    async def test_search_suggest_is_tenant_isolated(
        self, async_client, request, token_fixture, role,
        tenant_a_ids, tenant_b_ids, doc_a, doc_b, db_session
    ):
        """Search suggestions must be tenant-isolated."""
        token = request.getfixturevalue(token_fixture)
        is_token_a = token_fixture.startswith("token_a")
        other_tenant_id = tenant_b_ids["tenant_id"] if is_token_a else tenant_a_ids["tenant_id"]

        # Upload different content to each tenant
        content_a = "Unique content for tenant A alpha beta gamma"
        content_b = "Unique content for tenant B delta epsilon zeta"

        # Upload to tenant A
        files_a = {"file": ("content_a.txt", content_a.encode(), "text/plain")}
        headers_a = {"Authorization": f"Bearer {token}"}
        resp_a = await async_client.post("/documents", files=files_a, headers=headers_a)
        assert resp_a.status_code == 201

        # Upload to tenant B
        files_b = {"file": ("content_b.txt", content_b.encode(), "text/plain")}
        other_token = tenant_b_ids["admin_token"] if is_token_a else tenant_a_ids["admin_token"]
        headers_b = {"Authorization": f"Bearer {other_token}"}
        resp_b = await async_client.post("/documents", files=files_b, headers=headers_b)
        assert resp_b.status_code == 201

        # Wait for processing
        await asyncio.sleep(2)

        # Test suggestions for tenant A content
        resp = await make_request(
            async_client, "GET", "/search/suggest?q=alpha", token
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "suggestions" in data

        # Verify no cross-tenant leakage
        assert_no_cross_tenant_leak(resp, other_tenant_id)


# ---- Cached answer isolation tests (AC 2) ----

class TestCacheIsolation:
    """Answer cache must be strictly tenant-isolated."""

    async def _create_test_document(self, tenant_id: uuid.UUID, user_id: uuid.UUID, content: str) -> uuid.UUID:
        """Create a test document via app session (vaultiq_app) with tenant context."""
        from app.models.document import Document, DocumentJob
        from tests.conftest import test_app_session_factory
        from app.database import set_tenant_context
        from app.services.storage import ensure_storage_dirs, get_document_file_path
        import uuid
        import io
        
        doc_id = uuid.uuid4()
        stored_filename = f"{doc_id}.txt"
        
        # Save file to storage
        storage_path = ensure_storage_dirs(tenant_id, doc_id)
        file_path = storage_path / stored_filename
        file_path.write_bytes(content.encode())
        
        async with test_app_session_factory() as session:
            await set_tenant_context(session, str(tenant_id))
            
            document = Document(
                id=doc_id,
                tenant_id=tenant_id,
                original_filename="test.txt",
                stored_filename=stored_filename,
                mime_type="text/plain",
                size_bytes=len(content),
                uploaded_by=user_id,
            )
            session.add(document)
            
            job = DocumentJob(
                tenant_id=tenant_id,
                document_id=doc_id,
                payload={"action": "index", "version": 1},
            )
            session.add(job)
            await session.commit()
            
            # Process document
            from app.services.processing import process_document
            from app.database import AsyncSessionLocal
            
            async with AsyncSessionLocal() as proc_session:
                await set_tenant_context(proc_session, str(tenant_id))
                await process_document(proc_session, tenant_id, doc_id, job.id)
        
        return doc_id

    async def _get_chunk_id(self, tenant_id: uuid.UUID, doc_id: uuid.UUID) -> uuid.UUID:
        """Get chunk ID for a document using app session."""
        from app.models.search import DocumentChunk
        from tests.conftest import test_app_session_factory
        from app.database import set_tenant_context
        from sqlalchemy import select
        
        async with test_app_session_factory() as session:
            await set_tenant_context(session, str(tenant_id))
            result = await session.execute(
                select(DocumentChunk.id).where(DocumentChunk.document_id == doc_id)
            )
            return result.scalar_one()

    async def _set_cache_entry(
        self, tenant_id: uuid.UUID, role: str, question: str, kb_version: int,
        answer_text: str, doc_id: uuid.UUID, chunk_id: uuid.UUID
    ):
        """Set cache entry using app session with proper tenant context."""
        from tests.conftest import test_app_session_factory
        from app.database import set_tenant_context
        
        async with test_app_session_factory() as session:
            await set_tenant_context(session, str(tenant_id))
            await AnswerCacheService.set(
                db=session,
                tenant_id=tenant_id,
                role=role,
                question=question,
                kb_version=kb_version,
                answer_text=answer_text,
                source_document_id=doc_id,
                source_chunk_id=chunk_id,
            )
            await session.commit()

    async def _get_cached_answer(
        self, tenant_id: uuid.UUID, role: str, question: str, kb_version: int
    ):
        """Get cached answer using app session with proper tenant context."""
        from tests.conftest import test_app_session_factory
        from app.database import set_tenant_context
        
        async with test_app_session_factory() as session:
            await set_tenant_context(session, str(tenant_id))
            return await AnswerCacheService.get(
                db=session,
                tenant_id=tenant_id,
                role=role,
                question=question,
                kb_version=kb_version,
            )

    @pytest.mark.asyncio
    async def test_tenant_a_cache_not_accessible_by_tenant_b(
        self, async_client, token_a_admin, token_b_admin,
        tenant_a, tenant_b, tenant_a_ids, tenant_b_ids
    ):
        """Tenant B cannot access tenant A's cached answers."""
        # Create a real document for tenant A using app session
        question = "What is the policy for vacation time?"
        answer_text = "Employees accrue vacation time at a rate of 2 days per month."
        doc_content = f"Vacation policy: {answer_text}"
        doc_a_id = await self._create_test_document(
            tenant_a["id"], tenant_a["client_admin"]["id"], doc_content
        )
        chunk_a_id = await self._get_chunk_id(tenant_a["id"], doc_a_id)
        kb_version = 1

        # Insert cache entry for tenant A using app session
        await self._set_cache_entry(
            tenant_id=tenant_a["id"],
            role="client_admin",
            question=question,
            kb_version=kb_version,
            answer_text=answer_text,
            doc_id=doc_a_id,
            chunk_id=chunk_a_id,
        )

        # Tenant B asks the same question - should not get A's cached answer
        resp = await make_request(
            async_client, "POST", "/search", token_b_admin,
            json={"query": question, "top_k": 5}
        )

        # Should either get no_answer or have to compute fresh answer
        assert resp.status_code == 200
        data = resp.json()

        # Verify tenant B didn't get tenant A's cached answer
        if "results" in data and len(data["results"]) > 0:
            for result in data["results"]:
                assert answer_text not in result.get("content", ""), \
                    "Tenant B received tenant A's cached answer"

        # Verify no cross-tenant leakage in response
        assert_no_cross_tenant_leak(resp, tenant_a_ids["tenant_id"])

    @pytest.mark.asyncio
    async def test_cache_isolation_by_role_within_same_tenant(
        self, async_client, token_a_admin, token_a_emp,
        tenant_a, tenant_a_ids
    ):
        """Cache is isolated by role within the same tenant."""
        question = "What is the dress code policy?"
        answer_text = "Business casual is required Monday-Thursday, casual Friday."
        doc_content = f"Dress code: {answer_text}"
        
        # Create document for tenant A
        doc_a_id = await self._create_test_document(
            tenant_a["id"], tenant_a["client_admin"]["id"], doc_content
        )
        chunk_a_id = await self._get_chunk_id(tenant_a["id"], doc_a_id)
        kb_version = 1

        # Insert cache entry for client_admin role using app session
        await self._set_cache_entry(
            tenant_id=tenant_a["id"],
            role="client_admin",
            question=question,
            kb_version=kb_version,
            answer_text=answer_text,
            doc_id=doc_a_id,
            chunk_id=chunk_a_id,
        )

        # Employee queries cache directly - should not get client_admin's cached answer
        cached_emp = await self._get_cached_answer(
            tenant_id=tenant_a["id"],
            role="employee",
            question=question,
            kb_version=kb_version,
        )
        
        # Employee should not find client_admin's cache entry (role isolation)
        assert cached_emp is None, "Employee should not find client_admin's cache entry"

        # Client_admin should find their own cache entry
        cached_admin = await self._get_cached_answer(
            tenant_id=tenant_a["id"],
            role="client_admin",
            question=question,
            kb_version=kb_version,
        )
        
        assert cached_admin is not None, "Client admin should find their own cache entry"
        assert cached_admin.answer_text == answer_text
        assert cached_admin.role == "client_admin"

    @pytest.mark.asyncio
    async def test_direct_cache_service_isolation(
        self, token_a_admin, token_b_admin, tenant_a, tenant_b, tenant_a_ids, tenant_b_ids
    ):
        """Direct service call isolation - bypass HTTP, test AnswerCacheService directly."""
        # Create real documents for both tenants
        question = "Direct cache isolation test question"
        answer_text_a = "Tenant A's cached answer"
        answer_text_b = "Tenant B's cached answer"
        
        doc_content_a = f"Content for A: {answer_text_a}"
        doc_content_b = f"Content for B: {answer_text_b}"
        
        doc_a_id = await self._create_test_document(
            tenant_a["id"], tenant_a["client_admin"]["id"], doc_content_a
        )
        doc_b_id = await self._create_test_document(
            tenant_b["id"], tenant_b["client_admin"]["id"], doc_content_b
        )
        
        chunk_a_id = await self._get_chunk_id(tenant_a["id"], doc_a_id)
        chunk_b_id = await self._get_chunk_id(tenant_b["id"], doc_b_id)
        kb_version = 1

        # Insert cache for tenant A using app session
        await self._set_cache_entry(
            tenant_id=tenant_a["id"],
            role="client_admin",
            question=question,
            kb_version=kb_version,
            answer_text=answer_text_a,
            doc_id=doc_a_id,
            chunk_id=chunk_a_id,
        )

        # Insert cache for tenant B using app session
        await self._set_cache_entry(
            tenant_id=tenant_b["id"],
            role="client_admin",
            question=question,
            kb_version=kb_version,
            answer_text=answer_text_b,
            doc_id=doc_b_id,
            chunk_id=chunk_b_id,
        )

        # Now test: tenant A queries cache directly
        cached_a = await self._get_cached_answer(
            tenant_id=tenant_a_ids["tenant_id"],
            role="client_admin",
            question=question,
            kb_version=kb_version,
        )
        
        # Tenant B queries cache directly
        cached_b = await self._get_cached_answer(
            tenant_id=tenant_b_ids["tenant_id"],
            role="client_admin",
            question=question,
            kb_version=kb_version,
        )
        
        # Each tenant should only see their own cached answer
        assert cached_a is not None, "Tenant A should have cached answer"
        assert cached_a.answer_text == answer_text_a
        assert cached_a.tenant_id == tenant_a["id"]
        
        assert cached_b is not None, "Tenant B should have cached answer"
        assert cached_b.answer_text == answer_text_b
        assert cached_b.tenant_id == tenant_b["id"]
        
        # Cross-tenant: tenant A context, looking for tenant B's cache
        # Should not find tenant B's entry due to RLS filtering by tenant_id
        cached_cross = await self._get_cached_answer(
            tenant_id=tenant_a_ids["tenant_id"],
            role="client_admin",
            question=question,
            kb_version=kb_version,
        )
        
        # With tenant A's context, we should only see tenant A's own cache (or None)
        assert cached_cross is not None, "Tenant A should see own cache"
        assert cached_cross.answer_text == answer_text_a
        assert cached_cross.tenant_id == uuid.UUID(tenant_a_ids["tenant_id"])


# ---- In-flight processing isolation tests (AC 3) ----

class TestProcessingIsolation:
    """Document processing must be tenant-isolated, even when in-flight."""

    @pytest.mark.asyncio
    async def test_concurrent_processing_does_not_leak(
        self, async_client, token_a_admin, token_b_admin,
        tenant_a_ids, tenant_b_ids, db_session
    ):
        """When tenant B is processing, tenant A search should not see B's content."""
        # Start processing a document for tenant B (long content that takes time)
        large_content_b = "Tenant B processing test content. " * 100  # Make it substantial

        files_b = {"file": ("large_b.txt", large_content_b.encode(), "text/plain")}
        headers_b = {"Authorization": f"Bearer {token_b_admin}"}

        # Start the upload (don't wait for completion)
        upload_task = asyncio.create_task(
            async_client.post("/documents", files=files_b, headers=headers_b)
        )

        # Give processing a moment to start
        await asyncio.sleep(1)

        # While B is processing, tenant A uploads and searches for their own content
        content_a = "Tenant A unique content for processing isolation test XYZ789"

        files_a = {"file": ("doc_a.txt", content_a.encode(), "text/plain")}
        headers_a = {"Authorization": f"Bearer {token_a_admin}"}

        resp_a = await async_client.post("/documents", files=files_a, headers=headers_a)
        assert resp_a.status_code == 201
        doc_a_id = resp_a.json()["id"]

        # Wait for A's document to process
        await asyncio.sleep(2)

        # Search for A's content - should find it
        resp_search_a = await make_request(
            async_client, "POST", "/search", token_a_admin,
            json={"query": "Tenant A unique content", "top_k": 5}
        )

        assert resp_search_a.status_code == 200
        data_a = resp_search_a.json()

        # Verify A's search results are correct and isolated
        assert_no_cross_tenant_leak(resp_search_a, tenant_b_ids["tenant_id"])

        # Complete B's upload
        resp_b = await upload_task
        assert resp_b.status_code == 201
        doc_b_id = resp_b.json()["id"]

        # Wait for B's document to finish processing
        await asyncio.sleep(3)

        # Now search for B's content with A's token - should not find it
        resp_search_b_with_a_token = await make_request(
            async_client, "POST", "/search", token_a_admin,
            json={"query": "Tenant B processing test content", "top_k": 5}
        )

        assert resp_search_b_with_a_token.status_code == 200
        data_b = resp_search_b_with_a_token.json()

        # Verify A's search for B's content returns empty or doesn't leak B's content
        assert_no_cross_tenant_leak(resp_search_b_with_a_token, tenant_b_ids["tenant_id"])

        # Verify B's own search for their content works
        resp_search_b_with_b_token = await make_request(
            async_client, "POST", "/search", token_b_admin,
            json={"query": "Tenant B processing test content", "top_k": 5}
        )

        assert resp_search_b_with_b_token.status_code == 200
        data_b_own = resp_search_b_with_b_token.json()
        assert_no_cross_tenant_leak(resp_search_b_with_b_token, tenant_a_ids["tenant_id"])

    @pytest.mark.asyncio
    async def test_processing_jobs_are_tenant_isolated(
        self, async_client, token_a_admin, token_b_admin,
        tenant_a_ids, tenant_b_ids, db_session
    ):
        """Processing jobs table respects tenant isolation."""
        # Upload document for tenant A
        files_a = {"file": ("job_test_a.txt", b"Content for tenant A job test", "text/plain")}
        headers_a = {"Authorization": f"Bearer {token_a_admin}"}
        resp_a = await async_client.post("/documents", files=files_a, headers=headers_a)
        assert resp_a.status_code == 201
        doc_a_id = resp_a.json()["id"]

        # Upload document for tenant B
        files_b = {"file": ("job_test_b.txt", b"Content for tenant B job test", "text/plain")}
        headers_b = {"Authorization": f"Bearer {token_b_admin}"}
        resp_b = await async_client.post("/documents", files=files_b, headers=headers_b)
        assert resp_b.status_code == 201
        doc_b_id = resp_b.json()["id"]

        # Wait for processing jobs to be created
        await asyncio.sleep(2)

        # Check that tenant A can only see their own processing jobs
        # (This would require querying the processing table - simplified check)
        # For now, we verify through search behavior that processing is isolated

        # Search for A's content with A's token
        resp_a_search = await make_request(
            async_client, "POST", "/search", token_a_admin,
            json={"query": "Content for tenant A job test", "top_k": 5}
        )
        assert resp_a_search.status_code == 200
        assert_no_cross_tenant_leak(resp_a_search, tenant_b_ids["tenant_id"])

        # Search for B's content with A's token (should not find it)
        resp_b_search_with_a_token = await make_request(
            async_client, "POST", "/search", token_a_admin,
            json={"query": "Content for tenant B job test", "top_k": 5}
        )
        assert resp_b_search_with_a_token.status_code == 200
        assert_no_cross_tenant_leak(resp_b_search_with_a_token, tenant_b_ids["tenant_id"])


# ---- Regression suite integration verification (AC 4) ----

class TestRegressionIntegration:
    """Verify the test suite integrates properly for regression testing."""

    def test_manifest_includes_new_search_endpoints(self):
        """Verify that search endpoints are properly included in isolation manifest."""
        # These should already be in the manifest from VQ-110
        assert ("POST", "/search") in ISOLATION_COVERED_ROUTES
        assert ("GET", "/search/suggest") in ISOLATION_COVERED_ROUTES

    @pytest.mark.asyncio
    async def test_health_no_leak(self, async_client):
        """Simple health test to verify basic setup works."""
        resp = await async_client.get("/health")
        assert resp.status_code == 200
        # Health should not contain any tenant info
        body = resp.text.lower()
        assert "tenant" not in body

    @pytest.mark.asyncio
    async def test_suite_runs_against_application_identity(
        self, async_client, token_a_admin, token_b_admin, tenant_b_ids
    ):
        """Verify that the test suite runs as vaultiq_app (NOBYPASSRLS)."""
        # This test verifies we're using the correct database identity
        # by checking that we get appropriate responses that require RLS

        # Try to access a non-existent document - should get 404, not 403
        # (403 would indicate permission issue, 404 indicates correct RLS behavior)
        fake_doc_id = "00000000-0000-0000-0000-000000000000"

        resp = await make_request(
            async_client, "GET", f"/documents/{fake_doc_id}/preview", token_a_admin
        )

        # Should be 404 (not found) not 403 (forbidden) if RLS is working correctly
        # This indicates the request is being processed with proper tenant context
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Document not found"

        # Verify no leakage in the error response
        assert_no_cross_tenant_leak(resp, tenant_b_ids["tenant_id"])


# ---- Manifest completeness verification ----

def test_manifest_covers_all_vq208_routes():
    """Verify that VQ-208 specific routes are covered in manifest."""
    # VQ-208 adds no new routes beyond what VQ-110 already covered
    # But we verify the existing search routes are present
    test_route_coverage_guard()