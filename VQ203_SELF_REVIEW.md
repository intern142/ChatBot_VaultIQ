# VQ-203 — Per-tenant document processing queue: Gate 4 self-review

Branch: `vq-203` · Reviewer: [lead]
Approach note: `APPROACH_VQ203.md`

## What this story does

Uploaded documents are read, split, embedded and indexed by a background worker
rather than in the request path, so one client uploading a large batch does not
slow down another.

## Acceptance criteria, walked one at a time

| AC | Criterion | Status | Evidence |
|----|-----------|--------|----------|
| 1 | Processing separate from live service | Met, with a caveat | `worker.py` is a separate entrypoint. Caveat: it is not yet wired into the Dockerfile, so "separate process" is a property of the code, not of the deployed system. |
| 2 | Job belongs to one tenant; cross-tenant write impossible | Met | `document_jobs.tenant_id` NOT NULL + FK, FORCE RLS. `test_cross_tenant_job_write_blocked` inserts a job with tenant A's context and tenant B's id and expects refusal. `test_tenant_a_cannot_enqueue_for_tenant_b` gets 404 on tenant B's document. |
| 3 | Per-tenant cap; other tenants progress | Met | `test_per_tenant_cap_enforced` now has a body: tenant A saturates its permits, tenant B acquires without blocking, A is genuinely blocked. `test_per_tenant_semaphore_limits_concurrency` covers the primitive. |
| 4 | Limited retries + readable failure reason | Met | `test_failed_job_retries_then_fails` drives `worker.process_job` with a failing pipeline and checks re-queue, retry_count, `last_error`, and the terminal `failed` state. `test_backoff_delays_the_retry` checks the delay actually moves `created_at`. |
| 5 | Client Admin sees status | Met | `GET /documents/{id}/status` returns status, error, timestamps, version and job detail. `test_status_endpoint_returns_full_info` asserts the shape; `test_status_endpoint_is_tenant_scoped` asserts tenant B gets 404 with no identifier in the body. |
| 6 | Re-running same version creates no duplicates | Met | Unique constraint on `(document_id, payload)` where payload carries the version. `test_reprocess_is_idempotent_same_version` checks one job per version. |
| 7 | Ready only when all answer data stored | Met | `test_ready_only_after_full_storage` fails the vector write and asserts the document is `failed`, not `ready`. `test_document_reaches_ready_with_chunks_stored` asserts `ready` implies chunks exist. |

## The part that matters most

The commit this review follows claimed 137 passing tests. Those tests did not
touch `process_document`, `store_chunks` or `worker.process_job`. All three
were broken and all three are now fixed:

- `alembic upgrade head` failed outright — two heads. A fresh database, which
  is what CI builds, could not be migrated at all.
- `process_document` raised `NameError: datetime` on its first line.
- `store_chunks` ran `CREATE TABLE` as `vaultiq_app`, which has no CREATE on
  schema public.
- Every write after a commit ran with no tenant context, because `set_config`
  is transaction-scoped.

No job had ever been processed. The queue accepted uploads and nothing consumed
them. `TestPipelineRunsEndToEnd` is the test that would have caught all four.

Four of the original tests were also vacuous — one had an empty body, two
asserted values they had just written by hand. Those are replaced. The count
went 137 → 152, but the number is not the point; the point is that 4 of the 11
original tests proved nothing and the new ones exercise real code paths.

## Cross-tenant verification

The tests that prove isolation use `app_session`, which connects as
`vaultiq_app` (NOBYPASSRLS) rather than the superuser. This is deliberate:
`tests/conftest.py` already carries a comment explaining that reusing the
application's `AsyncSessionLocal` would make every assertion vacuous, because
that session is wired to `settings.DATABASE_URL` — the superuser.

## Known defects still open

1. **The worker cannot see any job.** `dequeue_job` selects
   `FROM document_jobs WHERE status='queued'` with no tenant context, and the
   RLS policy hides every row from a no-tenant session. Verified directly:
   one job existed, `vaultiq_app` saw 0 rows with no context and 1 row with
   context. The worker would spin forever on an empty queue. **This blocks
   Gate 6 and needs a decision from the lead**, not a code fix — the options
   are a separate worker database identity, or round-robin across tenants with
   the tenant list read through a privileged path. Both change the threat
   model and neither is mine to choose.

2. **Embeddings cannot run offline.** `embed_chunks` imports `fastembed`,
   which is not in `requirements.txt` and downloads a model on first use. Rule
   2 forbids runtime downloads. The model has to be bundled at build time and
   the dependency pinned. The end-to-end test stubs this one function, so the
   rest of the pipeline is genuinely covered and this gap is explicit rather
   than hidden.

## Gate status

| Gate | Status |
|------|--------|
| 1 Approach note | Done |
| 2 Implement | Done |
| 3 Tests green | Done — 152 passed |
| 4 Self-review | This document |
| 5 Code review | Pending |
| 6 Live container | **Blocked** on the worker-dequeue defect above |
| 7 Demo | Pending |

Gate 6 is recorded as blocked rather than pending. Running the worker against
a live container would show it doing nothing, and presenting that as a pass
would be worse than recording the blocker.

## Notes for the reviewer

- The `document_chunks` table is created in the VQ-203 migration with a
  `vector(384)` column and the same `NULLIF` policy as every other tenant
  table. `CREATE EXTENSION IF NOT EXISTS vector` runs there rather than at
  request time.
- `chunk_text` is character-based, not token-based. The approach note asked
  whether 500/50 is acceptable; 500 *characters* is roughly 100-125 tokens, not
  500. If the intent was tokens this needs revisiting before search lands.
- This branch depends on VQ-201 (upload/category/quota) and VQ-202
  (approval/versioning), both unmerged. All three add a migration numbered
  `007`/`008` against the same parent, so they cannot merge without renumbering
  or a merge revision.
