# VQ-208 — Cross-tenant isolation test suite v2 (search level) — Approach Note

## Objective
Prove that **search itself cannot leak between tenants**, not just the operations around it.

## Dependencies Status
| Dependency | Branch | Status | Notes |
|------------|--------|--------|-------|
| VQ-205 (Search) | `vq-205` | ✅ Implemented | `app/services/search.py` — `hybrid_search`, `search_suggest`; uses tenant-scoped SQL with `tenant_id` binding |
| VQ-210 (Answer Cache) | `vq-210-tenant-cache` | ✅ Implemented | `app/services/answer_cache.py` — `AnswerCacheService.get/set/invalidate_tenant/get_kb_version`; RLS on `answer_cache` table; keyed by `(tenant_id, role, question_hash, kb_version)` |
| VQ-203 (Processing) | `vq-203` | ✅ Implemented | `app/services/processing.py` — document processing pipeline; `DocumentJob` with status; chunking + embedding + pgvector insert |

**Note:** None of these branches are merged to `main` (current `vq-208` is at `161eb6f`). The isolation suite must run against a branch that has all three merged, or we must merge them into a test integration branch. I will propose merging VQ-203/205/210 into `vq-208` first, then writing the suite.

## Test Strategy

### 1. Cross-tenant search isolation (AC 1)
- Create two tenants A and B
- Insert **identical document content** into both (same text, different doc/chunk IDs)
- Run hundreds of varied questions from tenant A against tenant A's index
- Verify **every result** has `document_id` belonging to tenant A
- Repeat for tenant B
- Edge cases: queries matching nothing, queries matching many, partial term overlap

### 2. Cached answer isolation (AC 2)
- Tenant A asks question Q → answer cached via `AnswerCacheService.set`
- Tenant B asks same question Q → **must not receive A's cached answer**
- Verify B gets fresh search result or no_answer, never A's `answer_text`
- Test both roles: `client_admin` and `employee` (separate cache namespaces per role)

### 3. In-flight processing isolation (AC 3)
- Tenant B uploads document, processing starts (job status = `processing`)
- Tenant A searches while B's document is being indexed
- Verify A **never sees** B's chunks/embeddings
- Test: interleaved commits during `store_chunks` (advisory lock + RLS)

### 4. Regression suite integration (AC 4)
- Add to CI: runs on any change to `app/services/search.py`, `app/services/answer_cache.py`, `app/services/processing.py`, `app/models/search.py`, `app/models/answer_cache.py`
- Nightly schedule in CI workflow

## Fixture Design (extends VQ-110)
Re-use `tenant_a`, `tenant_b`, `token_a_*`, `token_b_*` from `tests/conftest.py`.
Add:
- `search_doc_a` / `search_doc_b` — identical content docs in each tenant
- `search_chunks_a` / `search_chunks_b` — chunked + embedded in pgvector
- `answer_cache_entry_a` — pre-populated cache for tenant A

## Test Matrix

| Category | Tests | Method |
|----------|-------|--------|
| Search isolation | 10+ queries × 2 tenants | HTTP `POST /search` with auth tokens |
| Cache isolation | 5 questions × 2 roles × 2 tenants | Direct `AnswerCacheService` + HTTP |
| Processing isolation | 3 concurrent jobs | HTTP upload + poll job status + search during processing |
| Body leak checks | All responses | Assert no tenant B `document_id`/`chunk_id`/`content` in A's response |
| Coverage guard | Auto-discover `/search` + cache endpoints | Fail if any untested tenant-scoped operation added |

## Route Manifest (new entries)
Add to `tests/isolation_manifest.py`:
- `POST /search` (tenant-scoped)
- `POST /search/suggest` (tenant-scoped)  
- Cache endpoints if exposed via HTTP (check `app/routes/`)

## Implementation Steps

1. **Merge dependencies** into `vq-208`: cherry-pick or merge VQ-203, VQ-205, VQ-210
2. **Run migrations** — ensure `document_chunks` (pgvector), `answer_cache`, `document_jobs` tables exist
3. **Write `tests/test_isolation_suite_v2.py`** covering the 4 ACs
4. **Update `tests/isolation_manifest.py`** with new search/cache routes
5. **Add CI workflow** for nightly + on-change triggers
6. **Gate 3**: Run full suite, verify green
7. **Gate 4**: Self-review checklist
8. **Gate 6**: 
   - Run against live container (Docker + uvicorn)
   - Demonstrate: weaken `WHERE tenant_id = :tenant_id` in `hybrid_search` → show suite catches it (FAIL)
   - Restore, show suite PASS
9. **Gate 7**: Friday demo

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Dependencies not on main | Merge them into `vq-208` first; document any conflicts |
| pgvector similarity search leaks | RLS on `document_chunks` + explicit `tenant_id` binding in SQL (already in VQ-205) |
| Cache key collision across tenants | Cache key includes `tenant_id` + `role` + `kb_version` (VQ-210 design) |
| Processing commits drop tenant context | `set_tenant_context` called before each write (VQ-203 pattern) |
| Hundreds of queries slow | Parameterize; use 50 representative questions + random generation |

## Questions for Reviewer
1. Confirm: merge VQ-203/205/210 into `vq-208` before writing tests, or create separate integration branch?
2. Should cache isolation test via HTTP endpoint (if exists) or direct service call?
3. How many "hundreds of varied questions" — 50 representative + 50 generated, or full 200?
4. Nightly CI: use GitHub Actions `schedule` or separate workflow?

---
*Ready for reviewer approval before Gate 2 implementation.*