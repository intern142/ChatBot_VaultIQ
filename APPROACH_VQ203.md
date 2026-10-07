# VQ-203 — Per-tenant document processing queue (Approach Note)

Branch: `vq-203` (off `main`)
Sprint 3/Week 4 · P0 · 8 pts
Depends on: VQ-102 (DB isolation), VQ-201 (upload/category/quota — not yet merged)

## Objective

Uploaded documents are read, split and indexed in the background, per tenant, so a client uploading a large batch never slows down another client.

## Acceptance Criteria & Mechanisms

| AC | Criterion | Mechanism |
|----|-----------|-----------|
| 1 | Processing runs separately from live QA service | Dedicated background worker (ARQ/Redis or asyncio queue); not in request path |
| 2 | Each job belongs to one tenant + one document version; cross-tenant write impossible | Job row carries `tenant_id` + `document_id`; RLS on job table; worker sets tenant context before any write |
| 3 | Per-tenant concurrency cap; other tenants keep progressing | Token-bucket / semaphore per tenant in worker; global worker pool |
| 4 | Limited retries + human-readable failure reason | `retry_count` + `max_retries` on job; `last_error` text; exponential backoff |
| 5 | Client Admin sees status: queued/processing/ready/failed | `processing_status` enum on Document; `processing_error` text; GET `/documents/{id}/status` |
| 6 | Re-running same version = no duplicates | Job keyed by `(document_id, version)`; idempotent enqueue |
| 7 | Ready only when all answer data stored | Status = `ready` only after text extraction + chunking + embedding + index write all succeed |

## Architecture

### 1. Document model extensions (migration)

Add to `documents` table:
```sql
processing_status TEXT NOT NULL DEFAULT 'queued'  -- queued, processing, ready, failed
processing_error TEXT                             -- human-readable, set on failure
processing_started_at TIMESTAMPTZ
processing_completed_at TIMESTAMPTZ
processing_version INT NOT NULL DEFAULT 1         -- incremented on re-queue, for idempotency
```

RLS: inherits existing tenant policy (tenant_id already on table).

### 2. Processing job table (migration)

New table `document_jobs`:
```sql
CREATE TABLE document_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued',         -- queued, processing, done, failed
    retry_count INT NOT NULL DEFAULT 0,
    max_retries INT NOT NULL DEFAULT 3,
    last_error TEXT,
    payload JSONB NOT NULL DEFAULT '{}',           -- e.g., {"action": "index", "version": 1}
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    UNIQUE (document_id, payload)                  -- idempotency key
);
-- RLS: tenant_id = current_setting('app.current_tenant', true)::uuid
-- Index: (tenant_id, status, created_at) for fair dequeue
```

### 3. Background worker

- **Not in FastAPI process** — separate process (can be same container, different entrypoint)
- Uses `arq` (Redis-backed) or plain `asyncio.Queue` + PostgreSQL `FOR UPDATE SKIP LOCKED` dequeue
- **Fair dequeue**: `SELECT ... FROM document_jobs WHERE tenant_id = ? AND status = 'queued' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1` per tenant, round-robin across tenants
- **Per-tenant semaphore**: `asyncio.Semaphore(MAX_CONCURRENT_PER_TENANT)` in worker
- **Processing steps** (per job):
  1. Set job `status = 'processing'`, `started_at = now()`, document `processing_status = 'processing'`
  2. Load file from storage
  3. Extract text (reuse VQ-201 OCR/text extraction logic when merged; for now use existing text extraction)
  4. Split into chunks (configurable size/overlap)
  5. Embed chunks (FastEmbed, bundled at build time — no internet)
  6. Write chunks + embeddings to vector index (pgvector)
  7. On success: job `status = 'done'`, document `processing_status = 'ready'`, `processing_completed_at = now()`
  8. On failure: increment `retry_count`; if < `max_retries`, re-queue with backoff; else `status = 'failed'`, document `processing_status = 'failed'`, `processing_error = human_readable`

### 4. Fair scheduling

- Global worker pool: N concurrent workers (configurable)
- Per-tenant semaphore: `MAX_CONCURRENT_PER_TENANT = 2` (configurable)
- Dequeue loop round-robins across tenants that have queued jobs
- If a tenant hits cap, their jobs stay queued; other tenants proceed

### 5. Retry & failure

- `max_retries = 3` (configurable)
- Backoff: `2^retry_count * base_delay` (e.g., 30s, 60s, 120s)
- Human-readable error: map exception types → user-friendly messages
- After max retries: job `failed`, document `failed`, `processing_error` set

### 6. Client Admin visibility

- GET `/documents/{id}/status` → `{ document_id, processing_status, processing_error, processing_started_at, processing_completed_at, job: { status, retry_count, last_error } }`
- Requires `client_admin` role
- Cross-tenant protected by RLS

### 7. Idempotency

- Job unique key: `(document_id, payload)` — payload includes version/action
- Re-enqueue same version → existing job found, no duplicate

### 8. "Ready" semantics

- Document `processing_status = 'ready'` ONLY after:
  - Text extracted
  - Chunks created
  - Embeddings computed
  - All rows written to vector index
- If any step fails → `failed`, not `ready`

## Processing Pipeline (per document)

```
upload (VQ-201) → document row created with processing_status='queued'
       ↓
enqueue job (action='index', version=1) → document_jobs row
       ↓
worker dequeues → status='processing'
       ↓
extract text (pdf/txt/md/docx/xlsx/csv + OCR for images)
       ↓
split into chunks (500 tokens, 50 overlap)
       ↓
embed each chunk (FastEmbed)
       ↓
write to pgvector (chunks table with document_id, tenant_id, embedding)
       ↓
on ALL success → job done, document ready
on ANY failure → retry (up to 3) → then failed
```

## Database Changes

1. **Migration 001_vq203_processing.py** (on this branch):
   - Add `processing_status`, `processing_error`, `processing_started_at`, `processing_completed_at`, `processing_version` to `documents`
   - Create `document_jobs` table with RLS
   - Add indexes for fair dequeue

2. **Models**: Update `Document` model; add `DocumentJob` model

3. **Schemas**: `ProcessingStatusResponse`, `JobStatus` enum

## API Changes

- `POST /documents` → after upload, auto-enqueue processing job (action='index', version=1)
- `POST /documents/{id}/reprocess` (client_admin) → increment `processing_version`, enqueue new job
- `GET /documents/{id}/status` → processing status + job details

## Worker Entrypoint

- New script: `worker.py` — runs the async processing loop
- Config via env: `WORKER_CONCURRENCY`, `MAX_CONCURRENT_PER_TENANT`, `MAX_RETRIES`, `BASE_RETRY_DELAY`
- Can run multiple worker processes for horizontal scaling

## Testing

1. Unit: state machine, retry logic, idempotency
2. Integration: two tenants × 20 docs each, both progress, worker crash leaves no partial
3. Cross-tenant: tenant A cannot enqueue job for tenant B's document
4. Live container: statuses over time, kill/restart worker

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| VQ-201 not merged (category/quota/OCR) | Use existing text extraction; OCR stub; category field optional |
| No Redis in stack | Use PostgreSQL `FOR UPDATE SKIP LOCKED` for queue — no extra infra |
| Worker crash mid-job | Idempotent steps + `FOR UPDATE` on job row; partial pgvector writes cleaned on retry |
| Long-running processing blocks tenant | Per-tenant semaphore + small chunk size |

## Open Questions for Lead

1. **Worker deployment**: Same container different entrypoint, or separate service? (Affects Dockerfile)
2. **Redis vs PostgreSQL queue**: Brief says no internet; Redis is local but adds infra. PostgreSQL queue is simpler.
3. **Embedding model**: FastEmbed bundled? Confirm model name and bundling.
4. **Chunking params**: 500 tokens / 50 overlap — configurable?
5. **Vector index**: pgvector `ivfflat` or `hnsw`? When to create index (after bulk load)?
6. **VQ-201 merge timing**: This branch assumes basic upload works; category/quota/OCR can be added later.

---

## Implementation Order

1. Migration + models + schemas
2. Document status fields + auto-enqueue on upload
3. Job table + enqueue/dequeue logic
4. Worker skeleton + fair dequeue + per-tenant semaphore
5. Text extraction + chunking + embedding + pgvector write
6. Retry logic + failure handling
7. Status endpoint
8. Tests (unit + integration + cross-tenant)
9. Live container verify