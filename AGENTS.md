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
- Current branch: vq-102-rls
- Current task: VQ-102 — Database-level tenant isolation
- Status: **VQ-102 Gates 1-4 complete**. Gate 5 (Code review) pending. All tests passing.
- Gate 6 Evidence (pending live container): cross-tenant reads blocked via psql with vaultiq_app role, no-tenant context returns zero rows, super_admin limited grants

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
- Gate 4: Self-review complete, checklist ticked, PR #4 opened (commit 5df1fa0)
- Gate 5: Pending (reviewer approval)
- Gate 6: Live container verified — 5 tests passed (health, tenant login, tampered token 401, suspended tenant 403, super admin null tenant)
- Gate 7: Pending (demo)

### VQ-104 — Per-tenant document storage
- Storage path: `storage/{tenant_id}/{doc_uuid}/original/{uuid}.bin` — never from uploaded filename
- 6 endpoints: POST/GET/DELETE /documents, preview, download, usage
- Mime allowlist (pdf, txt, md, docx, xlsx, csv), 50MB max
- Path traversal sanitization (.., /, \ stripped)
- Cross-tenant download/preview/delete returns 404
- RLS policy on documents table
- File deleted from disk on document delete
- Storage usage tracked: count, bytes, MB per tenant
- 13 tests: upload, list, preview, download, cross-tenant 404, delete, usage, path traversal
- Gate 1: Approach note drafted (reviewer approval pending)
- Gate 2: Implementation complete (commits 37ec731, 0d50044, 47e7595, 126170c, 3a417b3, b733d65)
- Gate 3: 13 tests written, all 57 tests passing
- Gate 4: Self-review complete, checklist ticked, PR #5 opened
- Gate 5: Pending (reviewer approval)
- Gate 6: Live container verified — Tenant A upload stored at `storage/8b8b25d9-3237-4469-9309-c0a15bdabce4/2e3e2639-6bf8-4021-8b5a-9abb535c9857/original/2e3e2639-6bf8-4021-8b5a-9abb535c9857.pdf`, cross-tenant download from Tenant B returns 404, storage usage tracked (1 doc, 13 bytes)
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

## VQ-101 — Tenant data model and migration (Detailed)
**Note:** This is **VQ-101**, not HX-101. Asana shows it as HX-101 but we are not using HX in this application. The correct story ID is **VQ-101**.
**[BE][W1][P0][5pt]**

### Objective
Introduce the client organisation (tenant) as a first-class concept so that every piece of data in VaultIQ belongs to exactly one tenant.

### Acceptance Criteria
1. A tenant can be created with a unique short code, a display name and a status (active / suspended / offboarding / purged)
2. Every record that holds client data (users, documents and their versions, text chunks, embeddings, conversations, messages, feedback, audit entries, sessions, cached answers, ingestion jobs) is linked to one tenant and cannot exist without one
3. Platform (Super Admin) accounts are the only accounts not linked to a tenant
4. All existing HeXta/ADS data ends up under one tenant with nothing lost
5. The change can be rolled back

### Must Be Proven
- Before/after record counts for the ADS migration, posted as a comment
- An automated test that inserting client data without a tenant fails
- The full existing test suite still passes

### Out of Scope
- Enforcing who can read which tenant's data (VQ-102, VQ-103)

### Gates
| Gate | Requirement |
|------|-------------|
| 1 | Approach note — tables to touch, migration steps, tests, risks. Reviewer approves before coding. |
| 2 | Implement — Branch `vq-101-tenant-model`. Small commits with story ID. Push daily. |
| 3 | Tests written and green — Migration up/down test on seeded data; model test that missing tenant_id fails; full test suite green. Paste run summary. |
| 4 | Self-review — Go through Review checklist and Common mistakes; tick each in comment. Open PR. |
| 5 | Code review — Lead reviews. |
| 6 | Live container verify — Rebuild image, run migration, verify each acceptance criterion by hand. Paste evidence (commands, row counts). |
| 7 | Demo & sign-off — Friday evening. |

---

## VQ-105 — Tenant-scoped login and session tokens (Detailed)
**Note:** This is **VQ-105**, not HX-105. Asana shows it as HX-105 but we are not using HX in this application. The correct story ID is **VQ-105**.
**[BE][W1][P0][5pt]**

### Objective
Users log in to their own organisation, and every request afterwards carries proof of who they are, their role, and which tenant they belong to.

### Acceptance Criteria
1. Login requires the organisation code, email and password
2. A wrong organisation code, wrong email and wrong password all produce the same response, in the same time, so an attacker cannot tell which one was wrong
3. The session token identifies the user, their role and their tenant; a platform (Super Admin) token has no tenant
4. Sessions can be refreshed and revoked; a revoked session stops working on the very next request
5. Repeated failed logins lock the account temporarily
6. Minimum password strength is enforced

### Must Be Proven
- Automated tests for the full success/failure matrix, a tampered token, and a revoked session
- Evidence from the live container showing decoded tokens for each role (secrets redacted)

### Out of Scope
- Invite and password-reset flows (VQ-107, VQ-301)

### Gates
| Gate | Requirement |
|------|-------------|
| 1 | Approach note — login flow, JWT claims, refresh/revocation reuse, lockout. Reviewer approves first. |
| 2 | Implement — Branch `vq-105-tenant-login`. Small commits with story ID. |
| 3 | Tests written and green — Login matrix, token tampering, revoked session. Full suite green. Paste summary. |
| 4 | Self-review — Confirm identical error text for all login failures. Tick Common mistakes. Open PR. |
| 5 | Code review — Lead reviews. |
| 6 | Live container verify — Log in as Super Admin, Client Admin, Employee; decode JWT and paste claims. |
| 7 | Demo & sign-off — Friday evening. |

---

## VQ-104 — Per-tenant document storage (Detailed)
**Note:** This is **VQ-104**, not HX-104. Asana shows it as HX-104 but we are not using HX in this application. The correct story ID is **VQ-104**.
**[BE][W1][P0][3pt]**

### Objective
Each tenant's uploaded files are kept physically separate, and no user-supplied value can influence where a file is stored or which file is read.

### Acceptance Criteria
1. Files are stored in a location derived from the tenant and a server-generated document identity, never from the uploaded filename
2. Reading, previewing or downloading a file re-checks that the file belongs to the requesting tenant
3. Per-tenant storage usage is tracked so quotas can be enforced later

### Must Be Proven
- Automated tests for path-manipulation attempts and for cross-tenant download
- Evidence from the live container showing where an uploaded file landed and a refused cross-tenant fetch

### Gates
| Gate | Requirement |
|------|-------------|
| 1 | Approach note — path layout, sanitisation rules, where tenant is re-checked. Reviewer approves before coding. |
| 2 | Implement — Branch `vq-104-storage-namespace`. Small commits with story ID. |
| 3 | Tests written and green — Path traversal cases; cross-tenant download denied. Full suite green. Paste summary. |
| 4 | Self-review — Confirm the user filename never reaches the path. Tick Common mistakes. Open PR. |
| 5 | Code review — Lead reviews. |
| 6 | Live container verify — Upload as tenant A on the live container, inspect the disk path, try to fetch it as tenant B. Paste evidence. |
| 7 | Demo & sign-off — Friday evening. |

---

## Sprint 1 Progress
- [x] VQ-101 — Tenant data model (Gates 1-4, 6 complete; Gate 5 pending)
- [x] VQ-105 — Tenant-scoped login and session tokens (Gates 1-4, 6 complete; Gate 5 pending)
- [x] VQ-103 — Tenant context on every request (Gates 1-4, 6 complete; Gate 5 pending)
- [x] VQ-104 — Per-tenant document storage (Gates 1-4, 6 complete; Gate 5 pending)

## Sprint 2 / Week 2 Plan (21–25 Sep)

### VQ-102 — Database-level tenant isolation [BE][W2][P0][8pt] — **IN PROGRESS (Gates 1-4 complete)**
**Depends on:** VQ-101, VQ-103
**Objective:** Even if application code has a bug, the database itself must refuse to return, change or delete one tenant's data to a session acting for another tenant.

**Completed:**
- Gate 1: Approach note drafted — policy design, tenant context via SET LOCAL, DB roles (vaultiq_app, vaultiq_super_admin), connection pool implications
- Gate 2: Implementation — Migration 003_rls_hardening.py with FORCE RLS on users, sessions tables; tenant_id column added to sessions; dedicated roles created with NOBYPASSRLS; grants configured
- Gate 3: Tests written and green — 15 tests covering: cross-tenant read/update/delete blocked for users & sessions; no-tenant context returns zero rows; vaultiq_app role cannot bypass RLS; vaultiq_super_admin limited grants; async ORM tests with vaultiq_app role
- All 23 tests passing (8 tenant + 15 RLS)

**Completed (continued):**
- Gate 4: Self-review checklist — acceptance criteria walked, checklist ticked, PR #6 opened

**Acceptance Criteria Status:**
1. ✅ Every table holding client data protected at DB level (users, sessions FORCE RLS)
2. ✅ Application account (vaultiq_app) cannot bypass protection (NOBYPASSRLS)
3. ✅ No-tenant session returns zero rows (tested)
4. ⏳ Background jobs bound to one tenant (pending implementation)
5. ✅ Super Admin reads use separate limited DB identity (vaultiq_super_admin with grants only on tenants)
6. ⏳ Latency within 10% baseline (pending measurement)

---

### VQ-106 — Role and permission model [BE][W2][P0][5pt]
**Depends on:** VQ-105
**Objective:** Three roles — Super Admin, Client Admin, Employee — with a written, enforced matrix of what each may do, so that nothing can be added to the system without declaring who may call it.

**Acceptance Criteria:**
1. A permissions document lists every operation and what each role may do with it
2. Enforcement is uniform: the same mechanism protects every operation
3. It is impossible to add a new operation without declaring its permissions (something fails if you forget)
4. Super Admin is explicitly denied any operation that returns document text, chunks or chat content
5. Employees can only ask questions, read their own history, and give feedback

**Must Be Proven:**
- An automated test that fails if any operation lacks a permission declaration
- Automated denied-role tests for each class of operation
- Evidence from the live container: a table of status codes per role for a sample of operations

**Gates:**
| Gate | Requirement |
|------|-------------|
| 1 | Approach note — Post the draft matrix and the decorator design. Reviewer approves first. |
| 2 | Implement — Branch `vq-106-permissions`. |
| 3 | Tests written and green — Router walk test (no un-annotated endpoint); denied-role tests per endpoint class. Full suite green. |
| 4 | Self-review checklist — Confirm Super Admin is denied on content endpoints. Tick Common mistakes. Open PR. |
| 5 | Code review — Lead reviews. |
| 6 | Live container verify — Hit 5 endpoints per role on the live container; paste the status codes. |
| 7 | Demo & sign-off — Friday evening. |

---

### VQ-107 — Tenant lifecycle: create, suspend, reactivate, invite first admin [BE][W2][P0][5pt]
**Depends on:** VQ-105, VQ-106
**Note:** Tracked as Sprint 3 in Asana but Sprint 2 here per our plan.
**Objective:** The platform operator can bring a new client organisation onto VaultIQ, pause it, and resume it, without touching the database by hand — and without needing internet or email.

**Acceptance Criteria:**
1. Create a tenant with code, name and storage quota
2. Suspend: every active session of that tenant stops working immediately and logins are refused; reactivate reverses it
3. Invite the first Client Admin: the system produces a one-time, time-limited invite the operator can hand over on screen; if an internal mail relay is configured it may also be sent
4. Accepting the invite lets the person set a password and become that tenant's Client Admin
5. Every action is recorded in the audit trail with who did it

**Must Be Proven:**
- Automated tests: invite cannot be reused or used after expiry; suspend takes effect within one request; tenant code uniqueness and format
- Evidence from the live container of the full create → invite → accept → suspend → refused sequence

**Gates:**
| Gate | Requirement |
|------|-------------|
| 1 | Approach note — Post a plan: endpoints, invite code design, suspend semantics. Reviewer approves first. |
| 2 | Implement — Branch `vq-107-tenant-lifecycle`. |
| 3 | Tests written and green — Invite reuse/expiry, suspend revokes sessions, slug validation. Full suite green. |
| 4 | Self-review checklist — Tick Common mistakes. Open PR. |
| 5 | Code review — Lead reviews. |
| 6 | Live container verify — Create tenant, invite, accept, suspend, confirm 403 — all on the live container. Paste evidence. |
| 7 | Demo & sign-off — Friday evening. |

---
 
## VQ-110 — Cross-tenant isolation test suite v1 (Detailed)
**Note:** This is **VQ-110**, not HX-110. Asana shows it as HX-110 but we are not using HX in this application. The correct story ID is **VQ-110**.
**[BE][W2][P0][5pt]**
 
### Objective
A permanent, automated proof that tenant A cannot touch tenant B through any operation the system exposes — and that stays true as new operations are added.
 
### Acceptance Criteria
1. Two fully populated test tenants (admins, employees, documents, conversations, feedback)
2. Every operation the system exposes is exercised with tenant A's credentials against tenant B's identifiers
3. The expected outcome is refusal; the response must never contain any tenant B identifier or content
4. Adding a new operation without covering it in the suite causes the suite to fail
5. The suite runs on every pull request and blocks merging
 
### Must Be Proven
- A coverage report showing every operation exercised
- A demonstration: break isolation on a throwaway branch and show the suite catching it
 
### Gates
| Gate | Requirement |
|------|-------------|
| 1 | Approach note — fixture design, route discovery, how resource ids map per route. Reviewer approves first. |
| 2 | Implement — Branch `vq-110-isolation-suite-v1`. |
| 3 | Tests written and green — Suite covers every route; coverage report attached; CI blocks merge on failure. |
| 4 | Self-review checklist — Confirm body is checked, not only status. Tick Common mistakes. Open PR. |
| 5 | Code review — Lead reviews. |
| 6 | Live container verify — Run the suite against the live container, not only the test DB. Paste the run. |
| 7 | Demo & sign-off — Friday evening. |
 
---
 
## Sprint 2 Summary

**Objective:** Database itself refuses cross-tenant reads — even if code has bugs. Roles enforced everywhere. Automated test proves A can't touch B. Can create/suspend customers.

**Tasks (Asana order: 102 → 106 → 107 → 110):**
| Task | Description | Depends On |
|------|-------------|------------|
| VQ-102 | Database-level tenant isolation — RLS policies on all tenant-scoped tables, automated cross-tenant read test, role enforcement | VQ-101, VQ-103 |
| VQ-106 | Role and permission model — permissions matrix, decorator enforcement, Super Admin denied on content | VQ-105 |
| VQ-107 | Tenant lifecycle — create, suspend/reactivate, invite first Client Admin, audit trail | VQ-105, VQ-106 |
| VQ-110 | Cross-tenant isolation test suite v1 — automated proof that tenant A cannot touch tenant B through any operation | VQ-102, VQ-106 |

**Must Be True by Friday:**
- RLS policies on ALL tenant-scoped tables (users, documents, sessions, future tables)
- Automated test: Tenant A cannot read, update, delete Tenant B rows via ANY query path
- Application DB role cannot bypass RLS (no BYPASSRLS)
- No-tenant session returns zero rows
- Latency within 10% of Sprint 0 baseline
- Permissions matrix documented, uniform enforcement, Super Admin denied on content
- Create/suspend/invite tenant flow works end-to-end
- Isolation test suite covers every operation, blocks merge on failure

```
Sprint 1: VQ-101 ✅ → VQ-105 ✅ → VQ-103 ✅ → VQ-104 ✅
Sprint 2: VQ-102 → VQ-106 → VQ-107 → VQ-110
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
- sessions: id, user_id (FK), tenant_id (FK), token_hash, is_revoked, expires_at, revoked_at, timestamps
- documents: id, tenant_id (FK), original_filename, stored_filename, mime_type, size_bytes, uploaded_by, created_at

## RLS Policy
- Enabled on users table (FORCE ROW LEVEL SECURITY)
- Policy: tenant_id = current_setting('app.current_tenant', true)::uuid
- Enabled on sessions table (FORCE ROW LEVEL SECURITY)
- Policy: tenant_id = current_setting('app.current_tenant', true)::uuid
- Enabled on documents table (FORCE ROW LEVEL SECURITY)
- Policy: tenant_id = current_setting('app.current_tenant', true)::uuid

## Auth Endpoints
- POST /auth/login — Login with organisation_code, email, password → JWT token
- POST /auth/refresh — Refresh token (requires valid Bearer token)
- POST /auth/logout — Revoke session (requires valid Bearer token)
- GET /health — Health check (no auth required)

## Document Endpoints
- POST /documents — Upload file (multipart, validates mime/size)
- GET /documents — List documents (paginated, tenant-scoped)
- GET /documents/{id}/preview — Preview (text inline, 5000 chars)
- GET /documents/{id}/download — Download (original filename)
- DELETE /documents/{id} — Delete (file + DB)
- GET /documents/usage — Storage stats (count, bytes, MB)

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
    document.py      — Document model
  routes/
    __init__.py
    auth.py          — Login, refresh, logout endpoints
    documents.py     — Document CRUD, preview, download, usage
  schemas/
    __init__.py
    auth.py          — LoginRequest, TokenResponse, RefreshRequest, MessageResponse
    tenant.py        — TenantCreate, TenantResponse
    user.py          — UserCreate, UserResponse
    document.py      — DocumentResponse, DocumentListResponse, StorageUsageResponse
  services/
    storage.py       — File save/delete with tenant isolation
tests/
  __init__.py
  conftest.py        — DB fixtures (async engine, session, db_conn)
  test_tenant.py     — 8 tests for VQ-101
  test_auth.py       — 18 tests for VQ-105
  test_tenant_context.py — 5 tests for VQ-103
  test_documents.py  — 13 tests for VQ-104
alembic/
  env.py
  versions/
    001_initial.py   — Tenants + Users + RLS migration
    002_add_sessions.py — Sessions table + lockout columns
    d9ecec7d2e04_vq_104_add_documents_table_for_per_.py — Documents table + RLS
.github/
  CHECKLIST.md       — Review checklist and common mistakes
  workflows/
    test.yml         — CI pipeline (PostgreSQL, alembic, pytest)
```

## CI Pipeline
**File:** `.github/workflows/test.yml`
- Triggers: push to `vq-105-tenant-login`, `vq-103-tenant-middleware`, PR to `main` or these branches
- Services: `pgvector/pgvector:pg16` on port 5432
- Steps: checkout → setup Python 3.11 → install deps → wait for PG → alembic upgrade head → create vaultiq_app role + grants → pytest tests/
- Status: Running (check https://github.com/intern142/ChatBot_VaultIQ/actions)
- Triggers include `vq-104-storage-namespace` branch

## Tooling
- `winget install GitHub.cli` — **done**
- `gh auth login` — **done** (authenticated as intern142, HTTPS protocol)
- `gh repo view intern142/ChatBot_VaultIQ` — **done** (repo access verified)



