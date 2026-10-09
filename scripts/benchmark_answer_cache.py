"""Benchmark script for VQ-210: Tenant-scoped answer cache performance."""

import asyncio
import hashlib
import time
import uuid
from statistics import mean, stdev
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import get_settings
from app.models.answer_cache import AnswerCache
from app.models.document import Document
from app.models.tenant import Tenant
from app.models.user import User
from app.auth.password import hash_password
from app.services.answer_cache import AnswerCacheService


async def benchmark():
    settings = get_settings()
    
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with session_factory() as session:
        # Setup: create tenant, user, document
        tenant = Tenant(
            short_code="BENCH_TENANT",
            name="Benchmark Tenant",
            status="active",
            storage_quota_mb=2048,
            knowledge_base_version=1,
        )
        session.add(tenant)
        await session.flush()
        
        user = User(
            tenant_id=tenant.id,
            email="bench@tenant.com",
            password_hash=hash_password("StrongPass1!"),
            role="client_admin",
        )
        session.add(user)
        await session.flush()
        
        doc = Document(
            tenant_id=tenant.id,
            original_filename="policy.pdf",
            stored_filename="policy.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            uploaded_by=user.id,
        )
        session.add(doc)
        await session.flush()
        
        await session.commit()
        
        question = "What is the refund policy for enterprise customers?"
        role = "employee"
        kb_version = 1
        
        # Warm up
        await AnswerCacheService.get(session, tenant.id, role, question, kb_version)
        await session.commit()
        
        # Benchmark cache MISS (no entry exists)
        print("\n=== CACHE MISS Benchmark ===")
        miss_times = []
        for i in range(100):
            start = time.perf_counter()
            result = await AnswerCacheService.get(session, tenant.id, role, f"Question {i}?", kb_version)
            elapsed = time.perf_counter() - start
            miss_times.append(elapsed * 1000)  # ms
        
        print(f"Cache MISS (100 runs):")
        print(f"  Mean: {mean(miss_times):.2f} ms")
        print(f"  Stdev: {stdev(miss_times):.2f} ms")
        print(f"  Min: {min(miss_times):.2f} ms")
        print(f"  Max: {max(miss_times):.2f} ms")
        
        # Populate cache with 100 entries
        print("\n=== Populating cache (100 entries) ===")
        chunk_id = uuid.uuid4()
        for i in range(100):
            await AnswerCacheService.set(
                session,
                tenant_id=tenant.id,
                role=role,
                question=f"Question {i}?",
                kb_version=kb_version,
                answer_text=f"Answer {i}",
                source_document_id=doc.id,
                source_chunk_id=chunk_id,
            )
        await session.commit()
        
        # Warm up cache hits
        for i in range(10):
            await AnswerCacheService.get(session, tenant.id, role, f"Question {i}?", kb_version)
        await session.commit()
        
        # Benchmark cache HIT
        print("\n=== CACHE HIT Benchmark ===")
        hit_times = []
        for i in range(100):
            start = time.perf_counter()
            result = await AnswerCacheService.get(session, tenant.id, role, f"Question {i}?", kb_version)
            elapsed = time.perf_counter() - start
            hit_times.append(elapsed * 1000)  # ms
        
        print(f"Cache HIT (100 runs):")
        print(f"  Mean: {mean(hit_times):.2f} ms")
        print(f"  Stdev: {stdev(hit_times):.2f} ms")
        print(f"  Min: {min(hit_times):.2f} ms")
        print(f"  Max: {max(hit_times):.2f} ms")
        
        # Speedup calculation
        speedup = mean(miss_times) / mean(hit_times)
        print(f"\n=== Speedup: {speedup:.2f}x faster with cache ===")
        
        # Benchmark set operation
        print("\n=== CACHE SET Benchmark ===")
        set_times = []
        for i in range(100):
            start = time.perf_counter()
            await AnswerCacheService.set(
                session,
                tenant_id=tenant.id,
                role=role,
                question=f"New question {i}?",
                kb_version=kb_version,
                answer_text=f"New answer {i}",
                source_document_id=doc.id,
                source_chunk_id=uuid.uuid4(),
            )
            await session.commit()
            elapsed = time.perf_counter() - start
            set_times.append(elapsed * 1000)
        
        print(f"Cache SET (100 runs):")
        print(f"  Mean: {mean(set_times):.2f} ms")
        print(f"  Stdev: {stdev(set_times):.2f} ms")
        print(f"  Min: {min(set_times):.2f} ms")
        print(f"  Max: {max(set_times):.2f} ms")
        
        # Benchmark invalidate_tenant
        print("\n=== CACHE INVALIDATE Benchmark ===")
        invalidate_times = []
        for i in range(10):
            # Re-populate
            for j in range(10):
                await AnswerCacheService.set(
                    session,
                    tenant_id=tenant.id,
                    role=role,
                    question=f"Invalidate test {i}-{j}?",
                    kb_version=kb_version,
                    answer_text=f"Answer {i}-{j}",
                    source_document_id=doc.id,
                    source_chunk_id=uuid.uuid4(),
                )
            await session.commit()
            
            start = time.perf_counter()
            count = await AnswerCacheService.invalidate_tenant(session, tenant.id)
            await session.commit()
            elapsed = time.perf_counter() - start
            invalidate_times.append(elapsed * 1000)
        
        print(f"Cache INVALIDATE (10 runs, 10 entries each):")
        print(f"  Mean: {mean(invalidate_times):.2f} ms")
        print(f"  Stdev: {stdev(invalidate_times):.2f} ms")
        print(f"  Min: {min(invalidate_times):.2f} ms")
        print(f"  Max: {max(invalidate_times):.2f} ms")
        
        # Cleanup
        await session.execute(text("TRUNCATE answer_cache, documents, users, tenants CASCADE"))
        await session.commit()
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(benchmark())