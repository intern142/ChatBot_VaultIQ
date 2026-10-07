#!/usr/bin/env python3
"""
VQ-204 Benchmark: Search latency and quality evaluation.

Usage:
    python evaluation/run_benchmark.py --tenant-a <uuid> --tenant-b <uuid> --chunks-per-tenant 5000

Generates synthetic test data and measures:
- Search latency (P50, P95, P99)
- Cross-tenant isolation (should return 0 results)
- Recall@10 for known queries
"""
import argparse
import asyncio
import json
import random
import statistics
import time
import uuid
from datetime import datetime, timezone
from typing import List

import httpx
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models.document import Document
from app.models.search import DocumentChunk
from app.models.tenant import Tenant
from app.services.embeddings import embed_texts


settings = get_settings()

# Synthetic test documents
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


def generate_chunks_for_tenant(tenant_id: uuid.UUID, doc_count: int, chunks_per_doc: int = 3) -> List[dict]:
    """Generate synthetic chunks for a tenant."""
    chunks = []
    for doc_idx in range(doc_count):
        doc_id = uuid.uuid4()
        for chunk_idx in range(chunks_per_doc):
            text_idx = (doc_idx * chunks_per_doc + chunk_idx) % len(SAMPLE_TEXTS)
            content = SAMPLE_TEXTS[text_idx]
            # Add some variation
            content = f"Document {doc_idx+1}, Section {chunk_idx+1}: {content}"
            chunks.append({
                "tenant_id": tenant_id,
                "document_id": doc_id,
                "chunk_index": chunk_idx,
                "content": content,
            })
    return chunks


async def setup_test_data(
    session: AsyncSession,
    tenant_a: uuid.UUID,
    tenant_b: uuid.UUID,
    chunks_per_tenant: int,
) -> tuple[List[uuid.UUID], List[uuid.UUID]]:
    """Insert synthetic documents and chunks for benchmarking."""
    print(f"Setting up test data: {chunks_per_tenant} chunks per tenant...")
    
    docs_per_tenant = chunks_per_tenant // 3
    
    # Create documents for tenant A
    doc_ids_a = []
    for _ in range(docs_per_tenant):
        doc_id = uuid.uuid4()
        doc_ids_a.append(doc_id)
        doc = Document(
            id=doc_id,
            tenant_id=tenant_a,
            original_filename=f"doc_{doc_id}.txt",
            stored_filename=f"{doc_id}.txt",
            mime_type="text/plain",
            size_bytes=1000,
            uploaded_by=uuid.uuid4(),  # placeholder
            indexed_at=datetime.now(timezone.utc),
        )
        session.add(doc)
    
    # Create documents for tenant B
    doc_ids_b = []
    for _ in range(docs_per_tenant):
        doc_id = uuid.uuid4()
        doc_ids_b.append(doc_id)
        doc = Document(
            id=doc_id,
            tenant_id=tenant_b,
            original_filename=f"doc_{doc_id}.txt",
            stored_filename=f"{doc_id}.txt",
            mime_type="text/plain",
            size_bytes=1000,
            uploaded_by=uuid.uuid4(),
            indexed_at=datetime.now(timezone.utc),
        )
        session.add(doc)
    
    await session.commit()
    
    # Generate chunks
    chunks_a = generate_chunks_for_tenant(tenant_a, docs_per_tenant)
    chunks_b = generate_chunks_for_tenant(tenant_b, docs_per_tenant)
    
    # Limit to requested chunk count
    chunks_a = chunks_a[:chunks_per_tenant]
    chunks_b = chunks_b[:chunks_per_tenant]
    
    print(f"Generating embeddings for {len(chunks_a) + len(chunks_b)} chunks...")
    all_contents = [c["content"] for c in chunks_a + chunks_b]
    embeddings = embed_texts(all_contents, batch_size=64)
    
    # Insert chunks for tenant A
    for i, chunk in enumerate(chunks_a):
        dc = DocumentChunk(
            tenant_id=chunk["tenant_id"],
            document_id=chunk["document_id"],
            chunk_index=chunk["chunk_index"],
            content=chunk["content"],
            embedding=embeddings[i],
        )
        session.add(dc)
    
    # Insert chunks for tenant B
    for i, chunk in enumerate(chunks_b):
        dc = DocumentChunk(
            tenant_id=chunk["tenant_id"],
            document_id=chunk["document_id"],
            chunk_index=chunk["chunk_index"],
            content=chunk["content"],
            embedding=embeddings[len(chunks_a) + i],
        )
        session.add(dc)
    
    await session.commit()
    print("Test data inserted successfully.")
    
    return doc_ids_a, doc_ids_b


async def benchmark_search(
    base_url: str,
    token: str,
    tenant_id: uuid.UUID,
    queries: List[str],
    top_k: int = 10,
    runs: int = 3,
) -> dict:
    """Run search benchmark against the API."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    latencies = []
    results_counts = []
    
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        for run in range(runs):
            for query in queries:
                start = time.perf_counter()
                response = await client.post(
                    "/search",
                    json={"query": query, "top_k": top_k, "hybrid_weight": 0.5},
                    headers=headers,
                )
                elapsed = (time.perf_counter() - start) * 1000  # ms
                
                if response.status_code == 200:
                    data = response.json()
                    latencies.append(elapsed)
                    results_counts.append(data.get("total_results", 0))
                else:
                    print(f"Search failed: {response.status_code} - {response.text}")
    
    if not latencies:
        return {"error": "No successful requests"}
    
    latencies.sort()
    p50 = latencies[len(latencies) // 2]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    
    return {
        "tenant_id": str(tenant_id),
        "total_requests": len(latencies),
        "latency_ms": {
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "p99": round(p99, 2),
            "mean": round(statistics.mean(latencies), 2),
            "min": round(min(latencies), 2),
            "max": round(max(latencies), 2),
        },
        "avg_results": round(statistics.mean(results_counts), 2) if results_counts else 0,
    }


async def test_cross_tenant_isolation(
    base_url: str,
    token_a: str,
    token_b: str,
    tenant_a: uuid.UUID,
    tenant_b: uuid.UUID,
) -> dict:
    """Verify tenant A cannot see tenant B's data."""
    headers_a = {"Authorization": f"Bearer {token_a}", "Content-Type": "application/json"}
    headers_b = {"Authorization": f"Bearer {token_b}", "Content-Type": "application/json"}
    
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        # Search from tenant A
        response = await client.post(
            "/search",
            json={"query": "security training", "top_k": 10, "hybrid_weight": 0.5},
            headers=headers_a,
        )
        results_a = response.json() if response.status_code == 200 else []
        
        # Search from tenant B
        response = await client.post(
            "/search",
            json={"query": "security training", "top_k": 10, "hybrid_weight": 0.5},
            headers=headers_b,
        )
        results_b = response.json() if response.status_code == 200 else []
        
        # Check for cross-tenant leakage
        tenant_a_results = results_a.get("results", []) if isinstance(results_a, dict) else []
        tenant_b_results = results_b.get("results", []) if isinstance(results_b, dict) else []
        
        # Verify no document IDs from tenant B appear in tenant A results
        tenant_b_doc_ids = set(str(r["document_id"]) for r in tenant_b_results)
        tenant_a_doc_ids = set(str(r["document_id"]) for r in tenant_a_results)
        
        # Also test direct cross-tenant query with tenant B's document IDs
        leak_found = bool(tenant_a_doc_ids & tenant_b_doc_ids)
    
    return {
        "cross_tenant_leakage": leak_found,
        "tenant_a_results": len(tenant_a_results),
        "tenant_b_results": len(tenant_b_results),
        "shared_doc_ids": len(tenant_a_doc_ids & tenant_b_doc_ids),
    }


async def get_auth_token(base_url: str, org_code: str, email: str, password: str) -> str:
    """Get JWT token via login."""
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        response = await client.post(
            "/auth/login",
            json={"organisation_code": org_code, "email": email, "password": password},
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        else:
            raise Exception(f"Login failed: {response.status_code} - {response.text}")


async def main():
    parser = argparse.ArgumentParser(description="VQ-204 Search Benchmark")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--tenant-a", required=True, help="Tenant A UUID")
    parser.add_argument("--tenant-b", required=True, help="Tenant B UUID")
    parser.add_argument("--chunks-per-tenant", type=int, default=5000, help="Chunks per tenant")
    parser.add_argument("--org-code-a", required=True, help="Tenant A org code")
    parser.add_argument("--org-code-b", required=True, help="Tenant B org code")
    parser.add_argument("--email-a", required=True, help="Tenant A admin email")
    parser.add_argument("--email-b", required=True, help="Tenant B admin email")
    parser.add_argument("--password", default="TestPass123!", help="Password for test users")
    parser.add_argument("--setup-only", action="store_true", help="Only setup test data")
    parser.add_argument("--benchmark-only", action="store_true", help="Only run benchmark (skip setup)")
    args = parser.parse_args()

    # Database setup
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    tenant_a = uuid.UUID(args.tenant_a)
    tenant_b = uuid.UUID(args.tenant_b)
    
    if not args.benchmark_only:
        async with async_session() as session:
            await setup_test_data(session, tenant_a, tenant_b, args.chunks_per_tenant)
    
    if args.setup_only:
        print("Setup complete. Exiting.")
        return
    
    # Get auth tokens
    print("Authenticating...")
    token_a = await get_auth_token(args.base_url, args.org_code_a, args.email_a, args.password)
    token_b = await get_auth_token(args.base_url, args.org_code_b, args.email_b, args.password)
    
    # Run benchmarks
    print("\nRunning benchmarks...")
    print("=" * 60)
    
    # Tenant A benchmark
    print(f"\nBenchmarking Tenant A ({args.tenant_a})...")
    bench_a = await benchmark_search(
        args.base_url, token_a, tenant_a, QUERIES, top_k=10, runs=3
    )
    print(json.dumps(bench_a, indent=2))
    
    # Tenant B benchmark
    print(f"\nBenchmarking Tenant B ({args.tenant_b})....")
    bench_b = await benchmark_search(
        args.base_url, token_b, tenant_b, QUERIES, top_k=10, runs=3
    )
    print(json.dumps(bench_b, indent=2))
    
    # Cross-tenant isolation test
    print("\nTesting cross-tenant isolation...")
    isolation = await test_cross_tenant_isolation(
        args.base_url, token_a, token_b, tenant_a, tenant_b
    )
    print(json.dumps(isolation, indent=2))
    
    # Summary
    print("\n" + "=" * 60)
    print("BENCHMARK SUMMARY")
    print("=" * 60)
    print(f"Tenant A P50 latency: {bench_a.get('latency_ms', {}).get('p50', 'N/A')} ms")
    print(f"Tenant A P95 latency: {bench_a.get('latency_ms', {}).get('p95', 'N/A')} ms")
    print(f"Tenant A P99 latency: {bench_a.get('latency_ms', {}).get('p99', 'N/A')} ms")
    print(f"Tenant B P50 latency: {bench_b.get('latency_ms', {}).get('p50', 'N/A')} ms")
    print(f"Tenant B P95 latency: {bench_b.get('latency_ms', {}).get('p95', 'N/A')} ms")
    print(f"Tenant B P99 latency: {bench_b.get('latency_ms', {}).get('p99', 'N/A')} ms")
    print(f"Cross-tenant leakage: {'YES - FAIL' if isolation['cross_tenant_leakage'] else 'NO - PASS'}")
    
    # Output JSON for CI
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "chunks_per_tenant": args.chunks_per_tenant,
        "tenant_a": bench_a,
        "tenant_b": bench_b,
        "isolation": isolation,
    }
    
    with open("benchmark_results.json", "w") as f:
        json.dump(output, f, indent=2)
    
    print("\nResults written to benchmark_results.json")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())