# VQ-210 — Approach Note: Tenant-Scoped Answer Cache

## Objective
Implement a tenant-scoped answer cache that ensures:
1. Cached answers are only reused by the same tenant
2. Access scope (role) is part of the cache key
3. Knowledge base version bump invalidates cache entries
4. Zero cross-tenant leakage

## Cache Key Design

The cache key must be a deterministic hash of:
```
cache_key = hash(tenant_id + "|" + role + "|" + question_hash + "|" + kb_version)
```

Where:
- `tenant_id`: UUID of the tenant (from verified token)
- `role`: User's role (`client_admin` or `employee`) — different roles may have different document access
- `question_hash`: SHA-256 of the normalized question text (trim, lowercase)
- `kb_version`: Integer from `tenants.knowledge_base_version` — incremented when approved document set changes

This ensures:
- Tenant A never sees Tenant B's cached answers
- Different roles get separate cache entries (even within same tenant)
- Semantically identical questions (case/whitespace differences) hit the same cache
- KB version bump = full cache invalidation for that tenant

## Database Schema

New table: `answer_cache`

```sql
CREATE TABLE answer_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    role VARCHAR(50) NOT NULL,  -- 'client_admin' | 'employee'
    question_hash CHAR(64) NOT NULL,  -- SHA-256 hex
    kb_version INTEGER NOT NULL,
    answer_text TEXT NOT NULL,  -- The cached answer sentence
    source_document_id UUID NOT NULL REFERENCES documents(id),
    source_chunk_id UUID NOT NULL,  -- Reference to the chunk in vector store
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,  -- Optional TTL
    UNIQUE (tenant_id, role, question_hash, kb_version)
);

-- Index for fast lookups
CREATE INDEX idx_answer_cache_lookup ON answer_cache (tenant_id, role, question_hash, kb_version);
-- Index for invalidation by kb_version
CREATE INDEX idx_answer_cache_invalidate ON answer_cache (tenant_id, kb_version);
```

RLS Policy:
```sql
ALTER TABLE answer_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE answer_cache FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON answer_cache
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid);
```

## API Integration Points

The cache sits between the question-answering service and the response:

```
Question → Normalize → Compute cache_key → Check cache
    → Hit: Return cached answer (log hit)
    → Miss: Run retrieval/selection → Store in cache → Return answer
```

## Invalidation Strategy

1. **KB Version Bump**: When `tenants.knowledge_base_version` increments (on document approve/reject/archive), all cache entries for that tenant with old `kb_version` become stale. Next request with new `kb_version` will miss and repopulate.

2. **Optional TTL**: `expires_at` for safety against stuck versions.

## Implementation Plan

### Files to Create/Modify:

1. **Migration**: `alembic/versions/xxx_add_answer_cache.py` — Create `answer_cache` table with RLS
2. **Model**: `app/models/answer_cache.py` — SQLAlchemy model
3. **Schema**: `app/schemas/answer_cache.py` — Pydantic schemas (if needed for API)
4. **Service**: `app/services/answer_cache.py` — Cache lookup/store/invalidate logic
5. **Integration**: Hook into the question-answering flow (when it exists)
6. **Tests**: `tests/test_answer_cache.py` — Coverage for all ACs

### Cache Service Interface:

```python
class AnswerCache:
    async def get(self, tenant_id: UUID, role: str, question: str, kb_version: int) -> Optional[CachedAnswer]
    async def set(self, tenant_id: UUID, role: str, question: str, kb_version: int, answer: CachedAnswer) -> None
    async def invalidate_tenant(self, tenant_id: UUID) -> None  # On KB version bump
```

### RLS Verification:

The cache table uses the same `tenant_isolation` pattern as other tables. The coverage guard in `tests/isolation_manifest.py` must be updated to include the cache table.

## Gate 1 Deliverables

- [ ] This approach note posted for review
- [ ] Cache key design documented above
- [ ] Migration schema designed
- [ ] RLS policy specified

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Cache key collision | SHA-256 + tenant_id + role + kb_version = astronomically low collision probability |
| Stale cache on version bump | `kb_version` in key ensures natural invalidation; no manual invalidation needed |
| Cross-tenant leakage | RLS + composite unique key on (tenant_id, role, question_hash, kb_version) |
| Cache growth unbounded | TTL (`expires_at`) + periodic cleanup job (future) |
| Role escalation via cache | Role is part of key; employee cannot read client_admin cache entries |

## Gate 3 Test Matrix

| Test | Description |
|------|-------------|
| `test_same_tenant_same_role_hits_cache` | Same tenant, role, question → cache hit |
| `test_different_tenant_misses_cache` | Tenant B asks same question → cache miss |
| `test_different_role_misses_cache` | Same tenant, employee vs client_admin → cache miss |
| `test_kb_version_bump_invalidates` | Tenant A's KB version increments → cache miss |
| `test_question_normalization` | "What is X?" vs "what is x?" → same cache key |
| `test_rls_enforcement` | Raw SQL as vaultiq_app cannot cross tenant boundary |

## Gate 6 Live Container Verification

1. Deploy with cache enabled
2. Tenant A asks question → answer returned, logged as MISS
3. Tenant A asks same question → answer returned, logged as HIT
4. Tenant B asks same question → logged as MISS (no cross-tenant hit)
5. Tenant A's KB version bumped → next request MISS
6. Verify logs show correct hit/miss behavior