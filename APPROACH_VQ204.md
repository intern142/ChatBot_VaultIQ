# VQ-204 Approach Note: Tenant-Partitioned Search Index

## Objective
Build a tenant-partitioned search index so indexed text and vectors are physically grouped per tenant. New tenants get auto-prepared index space. Existing ADS data migrates into the new layout. Search quality unchanged.

---

## Current State (from VQ-201 branch)
- `Document` model has `extracted_text` (full text), `extraction_method`, `extraction_status`
- 19 MIME types supported, OCR for images/scanned PDFs
- Text extraction runs at upload time (blocking)
- Storage: `storage/{tenant_id}/{doc_id}/original/{uuid}.bin`
- RLS enforced on `documents` table via `app.current_tenant`

---

## Design Decisions

### 1. Search Architecture: PostgreSQL Native (tsvector + pgvector)
**Why**: No internet → no external search service. PostgreSQL 16 has mature FTS and pgvector.

| Layer | Technology | Purpose |
|-------|------------|---------|
| Keyword/BM25 | `tsvector` + GIN index | Exact phrase, prefix, ranking |
| Semantic/Vector | `pgvector` (HNSW) | Embedding similarity |
| Hybrid | Reciprocal Rank Fusion (RRF) | Combine both scores |

### 2. Tenant Partitioning: PostgreSQL Native Partitioning (Declarative)
**Why**: 
- Single logical table, physical isolation per tenant
- RLS policies work naturally on partitioned tables
- New tenant = `CREATE TABLE ... PARTITION OF ... FOR VALUES IN ('tenant-uuid')`
- No dynamic SQL in application code
- Scales to thousands of tenants

**Schema**:
```sql
-- Parent tables (no data, only structure)
CREATE TABLE document_chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id uuid NOT NULL,
    document_id uuid NOT NULL,
    chunk_index int NOT NULL,
    content text NOT NULL,
    content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    embedding vector(384),  -- FastEmbed default dim
    created_at timestamptz DEFAULT now()
) PARTITION BY LIST (tenant_id);

CREATE INDEX ON document_chunks USING GIN (content_tsv);
CREATE INDEX ON document_chunks USING hnsw (embedding vector_cosine_ops);
```

**Per-tenant partition** (auto-created at tenant creation):
```sql
CREATE TABLE document_chunks_tenant_<uuid> PARTITION OF document_chunks
FOR VALUES IN ('<tenant-uuid>');
```

### 3. Chunking Strategy
- **Size**: 500 tokens (~2000 chars) with 50 token overlap
- **Boundary**: Sentence-aware (split on `.!?` + newline)
- **Metadata**: `document_id`, `chunk_index`, `page_range` (if available)

### 4. Embedding Model: FastEmbed (BAAI/bge-small-en-v1.5)
- 384 dimensions, bundled at build time (no runtime download)
- Runs on CPU, ~50ms/chunk on modern hardware
- MIT license, no internet required

### 5. Processing Pipeline
```
Document Upload (VQ-201) 
    → extraction complete (extracted_text populated)
    → enqueue indexing job (async, per-tenant queue)
    → worker: chunk → embed → upsert into partition
    → mark document.indexed_at
```

**Queue**: Redis not available (no internet). Use **PostgreSQL advisory locks + `indexing_jobs` table**:
- Table: `indexing_jobs(id, tenant_id, document_id, status, attempts, created_at, started_at, completed_at, error)`
- Worker picks `status='pending' FOR UPDATE SKIP LOCKED` with tenant-scoped advisory lock
- Max 2 concurrent workers per tenant (configurable)

### 6. Tenant Auto-Provisioning
- Hook into `POST /admin/tenants` (VQ-107)
- After tenant insert: create partition + indexes in same transaction
- `vaultiq_super_admin` role has `CREATE` on schema for partition creation

### 7. ADS Migration
- One-time script: `scripts/migrate_ads_to_partitions.py`
- Reads legacy ADS tables, writes into `document_chunks` partitions
- Runs as `vaultiq` (superuser) before app starts as `vaultiq_app`

### 8. Search API (new endpoints)
```
POST /search              # Hybrid search (keyword + vector)
GET  /search/suggest      # Autocomplete (tsvector prefix)
```
- Both tenant-scoped via `app.current_tenant`
- Client Admin + Employee access

---

## Files to Create/Modify

### New Files
| File | Purpose |
|------|---------|
| `app/models/search.py` | `DocumentChunk` model, partitioned table DDL |
| `app/services/chunking.py` | Sentence-aware chunking |
| `app/services/embeddings.py` | FastEmbed wrapper (sync, batched) |
| `app/services/indexer.py` | Indexing worker (processes `indexing_jobs`) |
| `app/routes/search.py` | Search endpoints |
| `app/schemas/search.py` | Request/response schemas |
| `alembic/versions/010_search_index.py` | Migration: chunks table, partitions, indexes |
| `scripts/migrate_ads_to_partitions.py` | ADS data migration |
| `scripts/index_existing.py` | Re-index existing documents |
| `evaluation/run_benchmark.py` | Benchmark script (2 tenants × 5k chunks) |

### Modified Files
| File | Change |
|------|--------|
| `app/routes/admin.py` | After tenant create → create partition |
| `app/routes/documents.py` | On extraction complete → enqueue indexing job |
| `app/models/__init__.py` | Export `DocumentChunk` |
| `requirements.txt` | Add `fastembed`, `pgvector` (already in pgvector image) |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Partition count grows large (1000+) | PostgreSQL handles 10k+ partitions; monitor `pg_class` |
| Embedding latency blocks upload | Async queue; extraction already done at upload |
| Vector index build time | HNSW builds incrementally; `hnsw` index after 1k rows |
| Cross-tenant leakage in search | RLS on parent table + partition pruning; isolation tests |
| OOM on large document embeddings | Batch size = 32; stream chunks; config `EMBED_BATCH_SIZE` |

---

## Tests to Write

1. **Unit**: Chunking (boundaries, overlap, metadata)
2. **Unit**: Embedding wrapper (dimension, batch, determinism)
3. **Integration**: Partition created on tenant create
4. **Integration**: Indexing job processed end-to-end
5. **Integration**: Search returns only tenant's results
6. **Isolation**: Tenant A search never returns Tenant B chunks (add to isolation suite)
7. **Benchmark**: `run_benchmark.py` — latency P50/P95/P99, recall@10

---

## Gate 3 Acceptance (Tests Green)
- All new tests pass
- Full existing suite (137) stays green
- Isolation suite covers `/search` endpoints
- Benchmark runs and outputs JSON

---

## Gate 6 Evidence (Live Container)
- Create tenant A, tenant B via API
- Upload 5k chunks each (scripted)
- Run `run_benchmark.py` against live container
- Paste benchmark output + latency comparison
- Verify cross-tenant search returns 0 results

---

## Questions for Reviewer

1. **Partition strategy**: Native partitioning (above) vs schema-per-tenant? Native preferred for RLS simplicity.
2. **Embedding dimension**: 384 (bge-small) OK, or need 768/1024?
3. **Search endpoint**: Start with hybrid only, or also expose keyword-only/vector-only?
4. **Re-index trigger**: Document update? (VQ-202 approval/versioning) — defer to VQ-202.
5. **Benchmark dataset**: Synthetic or real ADS sample? Need ADS data sample for realism.