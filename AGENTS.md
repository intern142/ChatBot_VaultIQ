- **Anything not in the tenant's approved documents is not an answer** — Never let the system fill a gap with something plausible.
- **If a task feels ambiguous, that's usually deliberate** — decide, write your reasoning in the approach note, and let the reviewer push back. Guessing silently is the problem, not deciding.

---

## Project State
- Current branch: BE_clone (Sprint 1+2 merged, merging Sprint 3)
- Current task: **VQ-203** — Per-tenant document processing queue (merging from `vq-203`)
- Test suite: **200+ tests passing** (Sprint 1+2+VQ-201+VQ-202+VQ-203)
- Sprint 1 + Sprint 2 merged: VQ-101, 102, 103, 104, 105, 106, 107, 110
- Sprint 3 merging: VQ-201, 202, 203, 204, 210, 301, 302, 304, 305

## Known Defects (must be fixed before VQ-202)
1. **The test suite runs as `vaultiq`, which is `rolsuper = t, rolbypassrls = t`.** Every
   RLS policy is inert during test and CI runs. VQ-102's claim that "the database itself
   refuses cross-tenant reads" is therefore only proven by the handful of tests that use
   the `app_db_session` / `app_db_conn` fixtures — never through the HTTP endpoints.
   **FIXED:** `tests/conftest.py` now provides `app_db_engine` / `app_db_session`
   fixtures that connect as `vaultiq_app` (NOBYPASSRLS), and the full suite runs under
   RLS enforcement. **CI now also runs as `vaultiq_app`** (see CI Pipeline section).
2. **Super Admin auth is broken under the real production identity (`vaultiq_app`).**
   The policies on `users` and `sessions` are bare
   `tenant_id = current_setting('app.current_tenant', true)::uuid` with no branch for
   `tenant_id IS NULL`, but VQ-101 AC3 requires platform accounts to have no tenant.
   Consequences, reproduced against `vaultiq_app`:
   - `POST /auth/login` with `organisation_code=SUPER` → **401** (the user row is invisible)
   - inserting a super-admin session row → **InsufficientPrivilegeError** (RLS rejects the
     INSERT, so it would be a 500 even if login succeeded)
   Super Admin is the only role that can create a tenant, so this blocks VQ-202's live
   evidence as well as VQ-201's.
   **FIXED:** Migration `008_platform_access_superadmin` adds gated `platform_account_access`
   policies on `users` and `sessions` (require `app.platform_access = 'on'` and no tenant
   context). `apply_token_context` in `app/database.py` sets this context for super-admin
   tokens. `tests/test_platform_access.py` (25 tests) proves the fix works both ways:
   platform can act, tenants cannot become platform, and no context combination widens.

## Worker queue design (resolved on `vq-203`)
`dequeue_job` originally selected `FROM document_jobs WHERE status='queued'` with no
tenant context, and the RLS policy hides every row from a no-tenant session, so the
worker saw a permanently empty queue.

Resolved by **round-robin, with no privilege escalation**: migration 005 already grants
`SELECT` on `tenants` to `vaultiq_app`. That table is platform metadata (id, short code,
name, status) with no customer content, and is the same list a Super Admin already sees.
`list_active_tenants` is the only query the worker runs without a context; every claim
goes through the same tenant-scoped path the HTTP layer uses. Rejected alternatives were
a worker role that can read all tenants' job rows, and a `SECURITY DEFINER` claim
function — both widen what a database identity can see to fix a scheduling problem.

## Blockers
- **Embeddings cannot run offline.** `embed_chunks` imports `fastembed`, which is not in
  `requirements.txt` and downloads a model on first use. Rule 2 forbids runtime
  downloads. Needs the dependency pinned and the model bundled at build time. Every test
  and live run stubs this one function; the rest of the pipeline is real.
- **The worker is not in the Dockerfile.** AC1's "separate from the live service" is
  currently a property of the code, not of the deployed artifact.
- VQ-201 / VQ-202 / VQ-203 all add a migration against the same parent (`007`/`008`).
  They cannot merge without renumbering or a merge revision. PR #10 is already
  `CONFLICTING`.


## VQ-110 — Cross-tenant isolation test suite v1 (Merged to main)
> **Verification status: Gates 1-4 code complete. Gates 3 and 6 are being re-run.**
> The runs recorded below were executed as the `vaultiq` role, which is
> `rolsuper = t, rolbypassrls = t` — so every RLS policy was inert. The suite
> proves the application code refuses cross-tenant access; it does **not** yet
> prove the database refuses it. See Known Defects.
### Gate 1: Approach Note ✅
- `APPROACH_VQ110.md` written — fixture design, route manifest, coverage guard, test matrix, body leak checks

### Gate 2: Implementation ✅
- Created `tests/test_isolation_suite.py` — full cross-tenant isolation test suite
- Updated `tests/conftest.py` — fixtures create Session rows for JWT tokens (fixes 401 auth issues)
- `tests/isolation_manifest.py` — route manifest (single source of truth) already existed

**Test Coverage:**
- 2 fully populated tenants (A & B) with admin/employee users, documents, invites, sessions
- Coverage guard test (`test_route_coverage_guard`) — auto-discovers FastAPI routes, fails if any tenant-scoped route missing from manifest
- Cross-tenant tests for all routes in manifest:
  - Public: `/health`, `/auth/login`, `/invite/accept`
  - Authenticated: `/auth/refresh`, `/auth/logout`
  - Documents: POST/GET/GET/{id}/preview, GET/{id}/download, DELETE/{id}, GET/usage
  - Admin: POST/GET /admin/tenants, PATCH /admin/tenants/{id}/suspend|reactivate|invite, GET /admin/tenants/{id}/audit
- Body leak checks (`assert_no_cross_tenant_leak`) — verify no tenant B identifiers/content in responses
- Tenant detection: `token_fixture.startswith("token_a")` correctly identifies tenant

**Test Results:**
- Full suite: **137 passed** — 3 consecutive full runs (was 85 pass / 16 flakes before event loop fix)

### Gate 3: Tests Green ✅
- Full suite: `python -m pytest tests/ -q` → **137 passed** (3 consecutive full runs, ~2.5 min each)
- Coverage report: `VQ110_COVERAGE.md` — every tenant-scoped operation mapped to its exercising test, all 17 routes in manifest covered
- Coverage guard (`test_route_coverage_guard`) proves adding an operation without covering it in the suite fails CI

**Fixes applied during Gate 3:**
- `conftest.py`: Windows `WindowsSelectorEventLoopPolicy` + session-scoped `event_loop` fixture — fixes asyncpg event-loop flakes (`'NoneType' object has no attribute 'send'`, `Event loop is closed`)
- `conftest.py`: invite fixtures now create fresh tenants (INVTA/INVTB) — tenants A/B already had client admins so invites returned 400
- `test_documents.py`: fixtures `employee` → `client_admin` (DELETE + usage are client_admin-only post-VQ-106)
- `test_isolation_suite.py`: invite accept test verifies fresh tenant invite binds only to its tenant (no leak); admin-denied test eagerly resolves `token_b_*` (was crashing: fixture resolution inside running async loop)

### Gate 4: Self-Review ✅
- `VQ110_SELF_REVIEW.md` written — all 5 acceptance criteria walked and confirmed, checklist ticked
- Criterion 4 (adding a route without coverage fails the suite) **demonstrated live**: injected a throwaway `GET /documents/{id}/star` route → coverage guard reported `MISSING ROUTES: [('GET', '/documents/{document_id}/star')]`, then removed
- PR #9 opened against main — commits pushed

**CI fixes found during Gate 4 (first PR CI run):**
- `requirements.txt`: added `psycopg2-binary==2.9.9` — CI `alembic upgrade head` needs sync driver (was in vq-105 lineage, never landed on this branch lineage)
- `alembic/env.py`: honor `DATABASE_URL_SYNC` env var — alembic.ini hardcoded local port 5433, CI DB is on 5432, so migrations connected to the wrong host on CI
- `requirements.txt`: added `email-validator==2.1.0` — `app/schemas/tenant.py` uses pydantic `EmailStr`
- `alembic/versions/006_sessions_tenant_nullable.py`: `sessions.tenant_id` is NULL for super-admin sessions (VQ-101 AC3, model `nullable=True`), but migration 002 declared NOT NULL so fresh migrations (CI) rejected super-admin logins/fixtures; older/local DBs were already nullable. Round-trip upgrade→downgrade→upgrade verified

### Gate 6: Live Container Verify ✅ (being re-run)
- Started uvicorn `app.main:app` against Docker PG (port 5433) on 127.0.0.1:8000
- Ran full isolation suite with `LIVE_BASE_URL=http://127.0.0.1:8000` → **36/36 passed**
- uvicorn access log: **1672 real HTTP requests** over the wire (not in-process), including cross-tenant `GET /documents/{id}/preview|download` → **404 Not Found** with body `{"detail":"Document not found"}` (refusal without existence leak)
- Super-admin auth has a pre-existing RLS bug (users table FORCE RLS filters NULL-tenant in `get_current_user`); isolation suite itself passes because it uses token-based cross-tenant checks that don't require super-admin admin endpoints
- **Caveat:** uvicorn was connected as the `vaultiq` superuser, so RLS was inert during this run. Re-running as `vaultiq_app`.

### Next Gates (Pending)
- Gate 5: Code review
- Gate 7: Demo Friday
- **Gates 3 and 6: re-verification in progress** — the original runs were done as the RLS superuser, so they do not demonstrate that the *database* refuses cross-tenant access. Re-running with the app connected as `vaultiq_app` (NOBYPASSRLS).

## Completed
### VQ-101 — Tenant data model and migration ✅
- Project structure created
- SQLAlchemy models (Tenant, User)
- Alembic migration with RLS policies
- Tests written (8 tests)
- Committed and pushed to branch vq-101-tenant-model
- Gate 1: Requirements & planning complete
- Gate 2: Design & architecture complete
- Gate 3: Migration up/down verified, 8/8 tests pass (commit d9e8d63)
- Gate 4: Review checklist ticked, PR opened (commit 2af9433, PR #1, #2)
- Gate 5: Pending (reviewer approval)
- Gate 6: Live container verified, 8/8 tests pass
- Gate 7: Pending (demo in sprint review)

### VQ-105 — Tenant-scoped login and session tokens ✅
- Login endpoint (POST /auth/login) with organisation_code, email, password
- Super admin login (organisation_code=SUPER, no tenant lookup)
- JWT access tokens with tenant_id, role, session_id
- Token refresh (POST /auth/refresh) with session rotation
- Token revocation on logout (POST /auth/logout)
- Account lockout after 5 failed attempts (15 min duration)
- 200ms constant response time on all auth outcomes
- Uniform error messages (no user enumeration)
- Session model for token tracking (migration 002)
- Lockout columns on users table (migration 002)
- 18 auth tests (password strength, login, lockout, token, revocation)
- All 26 tests passing (18 auth + 8 tenant)
- Fix asyncpg event loop issue in tests (httpx.AsyncClient)
- Fix super_admin login to skip tenant lookup
- **CI pipeline added** (`.github/workflows/test.yml`)
- **psycopg2-binary added** for alembic migrations in CI
- **Pydantic V2 migration** — `class Config` → `model_config = ConfigDict(...)` in config.py, tenant.py, user.py (removed deprecation warnings)
- Gate 1: Requirements & planning complete
- Gate 2: Design & architecture complete
- Gate 3: Implementation complete, 26/26 tests pass (commit 60eca71, 83966e0)