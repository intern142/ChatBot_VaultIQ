#!/usr/bin/env python3
"""
Setup test data for VQ-205 live container benchmark.
Creates two tenants with client_admin users, uploads documents, runs indexing.
"""
import asyncio
import uuid
import os
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

from app.config import get_settings
from app.auth.password import hash_password
from app.auth.jwt import create_access_token
from app.services.embeddings import embed_texts
from app.models.document import Document
from app.models.search import DocumentChunk, IndexingJob


settings = get_settings()

# Use admin database URL (vaultiq superuser) to bypass RLS for setup
DATABASE_URL = settings.DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

SAMPLE_TEXTS = [
    "The company policy requires all employees to complete annual security training.",
    "Vacation requests must be submitted at least two weeks in advance.",
    "The IT department manages all software licenses and hardware procurement.",
    "Remote work is permitted up to three days per week with manager approval.",
    "Expense reports over $500 require director-level approval.",
    "All confidential documents must be stored in the secure document management system.",
    "The incident response plan is reviewed and updated quarterly.",
    "New hires must complete onboarding within their first 30 days.",
    "Performance reviews are conducted semi-annually in June and December.",
    "The data retention policy specifies a 7-year retention period for financial records.",
    "Access to production systems requires multi-factor authentication.",
    "The business continuity plan includes off-site backup procedures.",
    "Vendor assessments are required before signing any new contracts.",
    "Employee personal information is protected under the privacy policy.",
    "The disaster recovery plan is tested annually with a full failover exercise.",
    "Code reviews are mandatory for all changes to production systems.",
    "The acceptable use policy prohibits personal use of company resources.",
    "Security patches must be applied within 30 days of release.",
    "The change management process requires approval for all production changes.",
    "Backup verification is performed weekly by the operations team.",
]

QUERIES = [
    "security training requirements",
    "vacation request policy",
    "software license management",
    "remote work guidelines",
    "expense approval limits",
    "confidential document storage",
    "incident response procedures",
    "new hire onboarding process",
    "performance review schedule",
    "data retention period",
    "production access requirements",
    "business continuity planning",
    "vendor assessment process",
    "employee privacy protection",
    "disaster recovery testing",
    "code review requirements",
    "acceptable use restrictions",
    "security patch timeline",
    "change management approval",
    "backup verification frequency",
]


async def setup_test_data(chunks_per_tenant: int = 100):
    """Create tenants, users, documents, chunks with embeddings."""
    async with session_factory() as db:
        # Create tenant A
        result = await db.execute(text("""
            INSERT INTO tenants (short_code, name, status, storage_quota_mb)
            VALUES ('TENANT_A', 'Tenant A', 'active', 2048)
            ON CONFLICT (short_code) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
        """))
        tenant_a = result.scalar()
        
        # Create tenant B
        result = await db.execute(text("""
            INSERT INTO tenants (short_code, name, status, storage_quota_mb)
            VALUES ('TENANT_B', 'Tenant B', 'active', 2048)
            ON CONFLICT (short_code) DO UPDATE SET name = EXCLUDED.name
            RETURNING id
        """))
        tenant_b = result.scalar()
        
        await db.commit()
        print(f"Tenant A: {tenant_a}")
        print(f"Tenant B: {tenant_b}")
        
        # Create client_admin users (delete first if exists)
        ph = hash_password("TestPass123!")
        
        await db.execute(text("DELETE FROM users WHERE email IN ('admin_a@tenant.com', 'admin_b@tenant.com')"))
        await db.commit()
        
        result = await db.execute(text("""
            INSERT INTO users (tenant_id, email, password_hash, role)
            VALUES (:tid, 'admin_a@tenant.com', :ph, 'client_admin')
            RETURNING id
        """), {"tid": tenant_a, "ph": ph})
        admin_a = result.scalar()
        
        result = await db.execute(text("""
            INSERT INTO users (tenant_id, email, password_hash, role)
            VALUES (:tid, 'admin_b@tenant.com', :ph, 'client_admin')
            RETURNING id
        """), {"tid": tenant_b, "ph": ph})
        admin_b = result.scalar()
        
        await db.commit()
        print(f"Admin A: {admin_a}")
        print(f"Admin B: {admin_b}")
        
        # Create sessions
        session_a = uuid.uuid4()
        session_b = uuid.uuid4()
        
        await db.execute(text("DELETE FROM sessions WHERE user_id IN (:uid1, :uid2)"), {"uid1": admin_a, "uid2": admin_b})
        await db.commit()
        
        await db.execute(text("""
            INSERT INTO sessions (id, user_id, tenant_id, token_hash, expires_at)
            VALUES (:sid, :uid, :tid, '', now() + interval '24 hours')
        """), {"sid": session_a, "uid": admin_a, "tid": tenant_a})
        
        await db.execute(text("""
            INSERT INTO sessions (id, user_id, tenant_id, token_hash, expires_at)
            VALUES (:sid, :uid, :tid, '', now() + interval '24 hours')
        """), {"sid": session_b, "uid": admin_b, "tid": tenant_b})
        
        await db.commit()
        print(f"Session A: {session_a}")
        print(f"Session B: {session_b}")
        
        # Create JWT tokens
        token_a = create_access_token(
            user_id=admin_a,
            role="client_admin",
            tenant_id=tenant_a,
            session_id=session_a,
        )
        token_b = create_access_token(
            user_id=admin_b,
            role="client_admin",
            tenant_id=tenant_b,
            session_id=session_b,
        )
        
        print(f"Token A: {token_a[:50]}...")
        print(f"Token B: {token_b[:50]}...")
        
        # Clear existing documents and chunks
        await db.execute(text("DELETE FROM document_chunks WHERE tenant_id IN (:ta, :tb)"), {"ta": tenant_a, "tb": tenant_b})
        await db.execute(text("DELETE FROM documents WHERE tenant_id IN (:ta, :tb)"), {"ta": tenant_a, "tb": tenant_b})
        await db.commit()
        
        # Create documents with extracted text
        docs_per_tenant = chunks_per_tenant // 3
        
        doc_ids_a = []
        doc_ids_b = []
        
        for i in range(docs_per_tenant):
            doc_id = uuid.uuid4()
            doc_ids_a.append(doc_id)
            doc = Document(
                id=doc_id,
                tenant_id=tenant_a,
                original_filename=f"doc_{i}.txt",
                stored_filename=f"{doc_id}.txt",
                mime_type="text/plain",
                size_bytes=1000,
                uploaded_by=admin_a,
                indexed_at=datetime.now(timezone.utc),
            )
            db.add(doc)
        
        for i in range(docs_per_tenant):
            doc_id = uuid.uuid4()
            doc_ids_b.append(doc_id)
            doc = Document(
                id=doc_id,
                tenant_id=tenant_b,
                original_filename=f"doc_{i}.txt",
                stored_filename=f"{doc_id}.txt",
                mime_type="text/plain",
                size_bytes=1000,
                uploaded_by=admin_b,
                indexed_at=datetime.now(timezone.utc),
            )
            db.add(doc)
        
        await db.commit()
        print(f"Created {len(doc_ids_a)} docs for tenant A, {len(doc_ids_b)} for tenant B")
        
        # Generate chunks with embeddings
        all_chunks = []
        for doc_id in doc_ids_a:
            for chunk_idx in range(3):
                text_idx = len(all_chunks) % len(SAMPLE_TEXTS)
                content = f"Document chunk: {SAMPLE_TEXTS[text_idx]}"
                all_chunks.append({
                    "tenant_id": tenant_a,
                    "document_id": doc_id,
                    "chunk_index": chunk_idx,
                    "content": content,
                })
        
        for doc_id in doc_ids_b:
            for chunk_idx in range(3):
                text_idx = len(all_chunks) % len(SAMPLE_TEXTS)
                content = f"Document chunk: {SAMPLE_TEXTS[text_idx]}"
                all_chunks.append({
                    "tenant_id": tenant_b,
                    "document_id": doc_id,
                    "chunk_index": chunk_idx,
                    "content": content,
                })
        
        # Limit to requested count
        chunks_a = [c for c in all_chunks if c["tenant_id"] == tenant_a][:chunks_per_tenant]
        chunks_b = [c for c in all_chunks if c["tenant_id"] == tenant_b][:chunks_per_tenant]
        
        print(f"Generating embeddings for {len(chunks_a) + len(chunks_b)} chunks...")
        all_contents = [c["content"] for c in chunks_a + chunks_b]
        embeddings = embed_texts(all_contents, batch_size=32)
        
        # Insert chunks
        for i, chunk in enumerate(chunks_a):
            dc = DocumentChunk(
                tenant_id=chunk["tenant_id"],
                document_id=chunk["document_id"],
                chunk_index=chunk["chunk_index"],
                content=chunk["content"],
                embedding=embeddings[i],
            )
            db.add(dc)
        
        for i, chunk in enumerate(chunks_b):
            dc = DocumentChunk(
                tenant_id=chunk["tenant_id"],
                document_id=chunk["document_id"],
                chunk_index=chunk["chunk_index"],
                content=chunk["content"],
                embedding=embeddings[len(chunks_a) + i],
            )
            db.add(dc)
        
        await db.commit()
        print(f"Inserted {len(chunks_a)} chunks for tenant A, {len(chunks_b)} for tenant B")
        
        # Save tokens for benchmark
        with open("benchmark_tokens.txt", "w") as f:
            f.write(f"TENANT_A={tenant_a}\n")
            f.write(f"TENANT_B={tenant_b}\n")
            f.write(f"TOKEN_A={token_a}\n")
            f.write(f"TOKEN_B={token_b}\n")
            f.write(f"ORG_A=TENANT_A\n")
            f.write(f"ORG_B=TENANT_B\n")
            f.write(f"EMAIL_A=admin_a@tenant.com\n")
            f.write(f"EMAIL_B=admin_b@tenant.com\n")
        
        print("Setup complete. Tokens saved to benchmark_tokens.txt")
        
        return {
            "tenant_a": str(tenant_a),
            "tenant_b": str(tenant_b),
            "token_a": token_a,
            "token_b": token_b,
        }


if __name__ == "__main__":
    asyncio.run(setup_test_data(100))