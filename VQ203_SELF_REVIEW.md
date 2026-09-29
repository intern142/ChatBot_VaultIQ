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

1. **Embeddings cannot run offline.** `embed_chunks` imports `fastembed`, which
   is not in `requirements.txt` and downloads a model on first use. Rule 2
   forbids runtime downloads. The model has to be bundled at build time and the
   dependency pinned. Every live and automated run above stubs this one
   function; the rest of the pipeline is real code. This is the only part of
   the pipeline not exercised for real.

## The worker-dequeue defect, and how it was resolved

The first version of this review recorded Gate 6 as blocked: `dequeue_job`
selected `FROM document_jobs WHERE status='queued'` with no tenant context, and
the policy hides every row from a no-tenant session, so the worker saw a
permanently empty queue.

The three options were a dedicated worker role that can read every job row
across every tenant, a `SECURITY DEFINER` claim function, or round-robin across
tenants using a tenant list read through a privileged path. The third was
chosen, and it turned out to need no privilege at all: migration 005 already
grants `SELECT` on `tenants` to `vaultiq_app`. That table is platform metadata
- id, short code, name, status - holds no customer content, and is the same
list a Super Admin already sees. So `list_active_tenants` is the only query the
worker runs without a context, and every actual claim happens through the same
tenant-scoped path the HTTP layer uses.

This is narrower than the alternatives rather than a compromise between them: no
new database role, no `SECURITY DEFINER` escape hatch, no policy loosened. A
test pins the worker identity to `vaultiq_app` with `BYPASSRLS` false, and
another parses the source of `list_active_tenants` to fail if a content table
is ever added to it.

## A second defect, found only by running the real worker

Gate 6 evidence was produced in two steps. Driving `dequeue_any_job` and
`process_document` directly worked immediately. Running `python worker.py` as a
real process drained nothing and printed nothing at all.

Three separate faults, none of which any test could have found:

1. **Concurrent indexing corrupted the index.** `MAX_CONCURRENT_PER_TENANT`
   allows several jobs for one tenant at once, so a re-upload landing while the
   previous version is still indexing puts two jobs on the same document. Both
   run DELETE-then-INSERT on `document_chunks`, and the second DELETE cannot
   see the first's newly inserted rows because its statement snapshot predates
   them - so it re-inserts the same `chunk_index` values and trips
   `uq_document_chunks_document_index`, leaving the index holding a mix of two
   versions. Fixed with a transaction-scoped `pg_advisory_xact_lock` on the
   document id, taken inside `store_chunks` where the delete and the insert
   share a transaction. Scoped per document, not per tenant, so parallelism
   between documents is unaffected and the lock cannot leak if a job dies.

2. **The run loop silently discarded exceptions.** Tasks that raised were never
   awaited, so failures surfaced as `Task exception was never retrieved` and the
   loop carried on looking idle. A queue that never drains is now
   indistinguishable from a worker with nothing to do, which is exactly the
   failure this story exists to prevent. The loop now retrieves every result or
   exception and logs it.

3. **`WORKER_CONCURRENCY` was read from the environment and never used.** The
   loop was strictly serial regardless of configuration.

The first of those is covered by
`TestConcurrentIndexingOfOneDocument`, which was verified to fail three times
out of three with the lock removed and pass three times out of three with it
restored. That matters more than the pass count: with only two concurrent jobs
the test passed even against the broken code, so the earlier version of it
would have been another vacuous test.

## Gate status

| Gate | Status |
|------|--------|
| 1 Approach note | Done |
| 2 Implement | Done |
| 3 Tests green | Done - 158 passed |
| 4 Self-review | This document |
| 5 Code review | Pending |
| 6 Live container | Done - see evidence below |
| 7 Demo | Pending |

## Gate 6 evidence

Run against the live database as `vaultiq_app`, `BYPASSRLS=False`, with the
worker started as a real process via `python worker.py`. Seeded three tenants
with four queued jobs each.

```
seeded: 3 tenants x 4 jobs = 12 queued
worker DATABASE_URL: ...vaultiq_app:vaultiq_secret
  [  5s] queued remaining: 0
tenant 0: document=ready  jobs[done=4]
tenant 1: document=ready  jobs[done=4]
tenant 2: document=ready  jobs[done=4]
RESULT: worker_loop drained and indexed every job
```

A second run drove the claim and process path directly and checked isolation:

```
worker identity : vaultiq_app   BYPASSRLS=False
enqueued        : 1 job for tenant A, 1 job for tenant B
tenants visible : 9
claim order     : ['06cbabfd', '7e374229']
tenant A       : document=ready  job=done  chunks=16
tenant B       : document=ready  job=done  chunks=16
tenant A sees tenant B's jobs: 0
RESULT: worker drained the queue under RLS
```

The queue is claimed across tenants by round-robin, both tenants reach `ready`
with chunks written, and tenant A cannot see tenant B's jobs. Only the
embedding call is stubbed in both runs.

Not yet demonstrated on a rebuilt container image: the worker is not in the
Dockerfile, so AC1's "separate from the live service" is a property of the
code and the process model, not of the deployed artifact. That is the remaining
gap for Gate 6, alongside the offline model.

## Notes for the reviewer

- The `document_chunks` table is created in the VQ-203 migration with a
  `vector(384)` column and the same `NULLIF` policy as every other tenant
  table. `CREATE EXTENSION IF NOT EXISTS vector` runs there rather than at
  request time.
- `chunk_text` is character-based, not token-based. The approach note asked
  whether 500/50 is acceptable; 500 *characters* is roughly 100-125 tokens, not
  500. If the intent was tokens this needs revisiting before search lands.
- The advisory lock is the only place `pg_advisory_xact_lock` is used. If a
  second writer is ever added to `document_chunks`, it must take the same lock.
- This branch depends on VQ-201 (upload/category/quota) and VQ-202
  (approval/versioning), both unmerged. All three add a migration numbered
  `007`/`008` against the same parent, so they cannot merge without renumbering
  or a merge revision.

