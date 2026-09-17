# VaultIQ Backend

## VaultIQ SOP — How We Work (from VaultIQ-Intern-SOP.docx)
**Build window:** 9 Sep – 8 Oct 2026 | **Shift:** 13:30 – 22:30
**Role:** Backend (Chaithanya) — Database, tenant isolation, login/permissions, document processing, search, answer selection, audit, offboarding

### Four Rules That Never Bend
1. **Tenant isolation is absolute** — Tenant A can never read/retrieve/list/search/cache-hit/infer anything from Tenant B (not documents, answers, usernames, not even that B exists)
2. **No internet** — Zero outbound network access in deployed stack. No cloud APIs, no runtime model downloads, no CDN, no telemetry
3. **No LLM, no generated text** — Answers are extracted sentences from customer docs only. Only ML artefacts: embedding model + reranker (bundled at build time)
4. **Platform operators see no customer content** — Super Admin sees counts/storage/health/usage only, never document text, chunks, questions, answers

### Seven Gates (must tick in order)
| Gate | Name | Requirement |
|------|------|-------------|
| 1 | Approach note | Post plan on story, wait for approval before coding |
| 2 | Implement | Small commits, story ID in every message, push daily |
| 3 | Tests green | Paste actual command + output. Existing suite must stay green |
| 4 | Self-review | Walk acceptance criteria one by one, confirm each, then open PR |
| 5 | Code review | Lead reviews (never other intern) |
| 6 | Live container verify | Rebuild, run, exercise, paste what you did + what came back |
| 7 | Demo & sign-off | Friday evening. Not demoed = not done |

### Daily Standup (by 14:00)
- Done yesterday:
- Doing today:
- Blocked by:
- Hours:

### Weekly Rhythm
- Frontend builds against mock spec during week, switches to real backend Friday
- Friday integration starts at 14:00 (not 20:00)

### Things That Get Story Sent Back
- Any path where data can cross tenants
- Anything reaching network at runtime
- Anything generating/paraphrasing text
- Gate 6 with only test output as evidence
- Acceptance criteria confirmed but not met
- Commits without story ID, or shift ending unpushed
- Implementation differing from approved approach note

---

## VaultIQ — Backend Track Brief (Intern3)
**Start:** Wed 9 Sep 2026 · **Go-live:** Fri 9 Oct 2026  
**Reviewer:** [lead name] · **Partner:** Intern4 (frontend)

### What We Are Building
A company gives us their documents — policies, HR rules, SOPs, process guides. Their staff ask questions in plain language. VaultIQ finds the answer inside those documents and returns it, showing which document it came from.
It does not write answers. It locates them. If the answer isn't in the documents, it says so.
We sell this to many companies at once from one installation. Each company is a tenant.

### Four Rules That Never Bend
1. **Tenant A can never see Tenant B's anything** — Not documents, not answers, not user names, not even the fact that B exists. This is the whole product. If it leaks once, we have no business.
2. **No internet** — The system runs with no outbound network access. No cloud APIs, no model downloads at runtime, no CDN, no telemetry.
3. **No LLM. No generated text** — Answers are sentences lifted from the customer's own documents. We are removing the AI-writing layer that exists in the old codebase.
4. **We (the platform operators) never see customer content** — We see how many documents a company has, not what's in them.

### What You Own (Everything the user doesn't see)
- The database and how tenants are kept apart in it
- Login, sessions, and who is allowed to do what
- Taking uploaded documents and turning them into something searchable
- The search itself, and picking the answer sentence
- The audit trail, exports, and deleting a customer completely when they leave

**You do not own:** any screen, any button, any CSS. If you find yourself editing the frontend, stop and talk to the lead.

### Your Month — Week by Week
| Week | What Must Be True by Friday |
|------|-----------------------------|
| Sprint 0 (9–11 Sep) | Your machine runs the existing system. You understand how a question becomes an answer today. Your first approach note is approved. |
| Week 1 (14–18 Sep) | A tenant exists as a real thing in the database. People log in to their own company. Every request knows which company it belongs to. Uploaded files land in that company's own folder. |
| Week 2 (21–25 Sep) | **Database itself refuses cross-tenant reads** — even if your own code has a bug. Roles are enforced everywhere. An automated test proves A can't touch B through any operation. We can create and suspend a customer. |
| Week 3 (28 Sep–2 Oct) | Documents get approved, versioned, processed and indexed — per tenant, with no customer able to starve another. Client admins can manage their staff. Dashboard numbers exist. |
| Week 4 (5–9 Oct) | Search is locked to one tenant. The AI-writing layer is gone. Audit export works. Offboarding wipes a customer completely. Everything proven on the running system, not just in tests. |

### How You Work — This Is Not Optional
**Every task has 7 gates as subtasks. You tick them in order.**

| Gate | Name | Requirement |
|------|------|-------------|
| 1 | Approach note | Before you write any code. Post a comment on the task: what you plan to do, which parts you'll touch, what could go wrong, what tests you'll write. Reviewer replies "approved" or asks you to think again. |
| 2 | Build it | Small commits, task ID in every message, push every day. |
| 3 | Tests | Write them, run them, paste the result in the task. The existing suite must stay green. |
| 4 | Self-review | Read acceptance criteria one by one and check your work against each. Comment confirming you did. Then open the PR. |
| 5 | Code review | Your reviewer reads it. If it comes back, that's normal and expected — it is not a failure. |
| 6 | Prove it on the running system | Rebuild the container and check it works for real. Screenshots, command output, whatever shows it. "The tests pass" is not proof. |
| 7 | Demo it Friday | If you didn't demo it, it isn't done. |

### Things We Track
- **Daily standup before 10:00** — what you finished yesterday, what you're on today, what's blocking you, hours. Missing this is recorded.
- **Every review rejection** is logged with what happened and why. Not to punish — to spot patterns and write final review with facts. Repeating the same mistake matters; making a new mistake doesn't.
- **Ask early** — Being stuck for two hours and asking is fine. Being stuck for two days silently is the one thing that will actually go badly for you.

### Where Things Live
- **Asana project "VaultIQ — One-Month Delivery"** — all your tasks. Work only from here.
- Your tasks start with **[BE]**.
- Ceremonies: Monday planning, Wednesday check-in, Friday integration + demo + retro.
- Day 1 of each week you publish the **interface spec** — the written description of what the screens can ask the engine for that week. Intern4 reviews it the same day and builds against a fake version of it. Friday is integration day: her screens connect to your real engine. If you change the spec mid-week without telling her, her week breaks.

### Honest Warnings
- **Week 2 is the hardest thing in the month** — Database-level isolation. Take it slowly, and use your approach note properly.
- **The single most common way this kind of system leaks** — a shared cache or a connection that remembers the previous request's tenant. Assume it will happen to you and test for it.
- **Anything not in the tenant's approved documents is not an answer** — Never let the system fill a gap with something plausible.
- **If a task feels ambiguous, that's usually deliberate** — decide, write your reasoning in the approach note, and let the reviewer push back. Guessing silently is the problem, not deciding.

---

## Project State
- Current branch: vq-103-tenant-middleware
- Current task: VQ-103 — Tenant context on every request
- Status: **VQ-105 Gate 6 complete**. VQ-103 Gate 1 (Approach note), Gate 2 (Implementation), Gate 3 (Tests) complete. Gate 4 (Self-review) pending.

## Blockers
- None

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

### VQ-105 — Tenant-scoped login and session tokens
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
- Gate 4: Review checklist added, PR opened (commit 08e40a6)
- Gate 5: Pending (reviewer approval)
- **Gate 6: Live container verified** — 26/26 tests pass against Docker PostgreSQL, health endpoint responds, login endpoint responds
- **Gate 6 Evidence — JWT Claims from live container logins:**
  - **Super Admin** (org_code=SUPER): `sub=<user_id>`, `role=super_admin`, `tenant_id=null`, `jti=<session_id>`, `exp=24h`
  - **Client Admin** (org_code=ACME): `sub=<user_id>`, `role=client_admin`, `tenant_id=d3985764-1cd6-4c25-baea-e73cefcc9fd6`, `jti=<session_id>`, `exp=24h`
  - **Employee** (org_code=ACME): `sub=<user_id>`, `role=employee`, `tenant_id=d3985764-1cd6-4c25-baea-e73cefcc9fd6`, `jti=<session_id>`, `exp=24h`

### VQ-103 — Tenant context on every request
- `set_tenant_context` helper in `app/database.py`
- `get_current_user_with_tenant` dependency in `app/auth/dependencies.py`
- Suspended/offboarding tenant check in login endpoint (`app/routes/auth.py`)
- 5 new tests: tampered token, cross-tenant 404, injected tenant_id ignored, suspended tenant blocked, super_admin bypass
- Gate 1: Approach note drafted (reviewer approval pending)
- Gate 2: Implementation complete (commit 4aaf703)
- Gate 3: 5 tests written, all 31 tests pass (commit 87af5ff)
- Gate 4: Self-review pending
- Gate 5: Pending (reviewer approval)
- Gate 6: Pending (live container verify)
- Gate 7: Pending (demo)

## Tech Stack
- Backend: FastAPI (Python 3.11)
- Database: PostgreSQL 16 (Docker: vaultiq-db, port 5433)
- ORM: SQLAlchemy 2.0 (async)
- Migrations: Alembic
- Auth: PyJWT (VQ-105)
- CI: GitHub Actions (PostgreSQL service, alembic, pytest)

---

## VQ-103 — Tenant context on every request (Detailed)
**Note:** This is **VQ-103**, not HX-103. Asana shows it as HX-103 but we are not using HX in this application. The correct story ID is **VQ-103**.
**[BE][W1][P0][3pt]**

### Objective
Exactly one place in the system decides which tenant a request belongs to, and it cannot be influenced by anything the caller sends other than a valid session token.

### Acceptance Criteria
1. The tenant for a request comes **only** from the verified session token
2. Any tenant identifier supplied elsewhere in the request is **not trusted**; the request is rejected or the value ignored (document which)
3. A request for a resource that belongs to another tenant is refused **without revealing** that the resource or the other tenant exists
4. Users of a **suspended or offboarding tenant** are refused on every operation except logout
5. Business logic **never has to parse the token** itself

### Must Be Proven
- Automated tests: tampered token, cross-tenant resource, injected tenant id, suspended tenant
- Evidence from the live container

### Gates
| Gate | Requirement |
|------|-------------|
| 1 | Approach note — where middleware sits, what it rejects, error codes. Reviewer approves before coding. |
| 2 | Implement — Branch `vq-103-tenant-middleware`. Small commits with story ID. |
| 3 | Tests written and green — Tampered token, cross-tenant resource, tenant_id in body, suspended tenant. Full suite green. |
| 4 | Self-review — Confirm no header-based tenant override remains. Tick Common mistakes. Open PR. |
| 5 | Code review — Lead reviews. |
| 6 | Live container verify — curl live container with tenant A token against tenant B ids; paste responses. |
| 7 | Demo & sign-off — Friday evening. |

---

## Sprint 1 Progress
- [x] VQ-101 — Tenant data model (Gates 1-4, 6 complete; Gate 5 pending)
- [x] VQ-105 — Tenant-scoped login and session tokens (Gates 1-4, 6 complete; Gate 5 pending)
- [ ] VQ-103 — Tenant context on every request (Gates 1-3 complete; Gate 4 pending)
- [ ] VQ-104 — Per-tenant document storage (depends on VQ-103)

## Task Dependency Chain
```
VQ-101 ✅ (Gates 1-4, 6) → VQ-105 ✅ (Gates 1-4, 6) → VQ-103 (Gates 1-3) → VQ-104
```

## Key Decisions
- Ignoring HeXta/ADS migration criterion (new application)
- Using pgvector for vector search (future)
- FastEmbed for embeddings (future)
- RLS at database level for tenant isolation
- VQ-105 before VQ-103 (dependency chain)
- Super admin login uses organisation_code=SUPER (no tenant)
- Password strength: min 8 chars, upper, lower, digit, special
- Lockout: 5 failed attempts → 15 min lockout

## Database Tables
- tenants: id, short_code, name, status, timestamps
- users: id, tenant_id (FK, nullable), email, password_hash, role, failed_login_attempts, locked_until, timestamps
- sessions: id, user_id (FK), token_hash, is_revoked, expires_at, revoked_at, timestamps

## RLS Policy
- Enabled on users table
- Policy: tenant_id = current_setting('app.current_tenant')::uuid

## Auth Endpoints
- POST /auth/login — Login with organisation_code, email, password → JWT token
- POST /auth/refresh — Refresh token (requires valid Bearer token)
- POST /auth/logout — Revoke session (requires valid Bearer token)
- GET /health — Health check (no auth required)

## Project Structure
```
app/
  __init__.py
  config.py          — Settings (pydantic-settings)
  database.py        — Async SQLAlchemy engine, session, Base
  main.py            — FastAPI app with routers
  auth/
    __init__.py
    password.py      — bcrypt hash/verify + strength validation
    jwt.py           — create_access_token, decode_token (PyJWT)
    dependencies.py  — get_current_user FastAPI dependency
  models/
    __init__.py
    base.py
    tenant.py        — Tenant model
    user.py          — User model
    session.py       — Session model (token tracking, revocation)
  routes/
    __init__.py
    auth.py          — Login, refresh, logout endpoints
  schemas/
    __init__.py
    auth.py          — LoginRequest, TokenResponse, RefreshRequest, MessageResponse
    tenant.py        — TenantCreate, TenantResponse
    user.py          — UserCreate, UserResponse
tests/
  __init__.py
  conftest.py        — DB fixtures (async engine, session, db_conn)
  test_tenant.py     — 8 tests for VQ-101
  test_auth.py       — 18 tests for VQ-105
alembic/
  env.py
  versions/
    001_initial.py   — Tenants + Users + RLS migration
    002_add_sessions.py — Sessions table + lockout columns
.github/
  CHECKLIST.md       — Review checklist and common mistakes
  workflows/
    test.yml         — CI pipeline (PostgreSQL, alembic, pytest)
```

## CI Pipeline
**File:** `.github/workflows/test.yml`
- Triggers: push to `vq-105-tenant-login`, PR to `main` or `vq-105-tenant-login`
- Services: `pgvector/pgvector:pg16` on port 5432
- Steps: checkout → setup Python 3.11 → install deps → wait for PG → alembic upgrade head → create vaultiq_app role + grants → pytest tests/
- Status: Running (check https://github.com/intern142/ChatBot_VaultIQ/actions)

## Tooling
- `winget install GitHub.cli` — **done**
- `gh auth login` — **done** (authenticated as intern142, HTTPS protocol)
- `gh repo view intern142/ChatBot_VaultIQ` — **done** (repo access verified)
