# VaultIQ Backend

> **File convention — read before doing anything.**
> This file holds only durable rules and reference. It must stay **byte-identical
> for every session, model and branch. Never edit this file.**
> All volatile state — current branch/task, gate progress, test counts, blockers,
> known defects, sprint plans, story history — lives in **`STATE.md`**, the only
> project file sessions may edit. Read `STATE.md` at session start; write updates
> there, never here. Changes to the reference below (new endpoint, table, file)
> happen only on the user's explicit request, on `main`.

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

## Key Decisions
- Ignoring HeXta/ADS migration criterion (new application)
- Using pgvector for vector search (future)
- FastEmbed for embeddings (future)
- RLS at database level for tenant isolation
- VQ-105 before VQ-103 (dependency chain)
- Super admin login uses organisation_code=SUPER (no tenant)
- Password strength: min 8 chars, upper, lower, digit, special
- Lockout: 5 failed attempts → 15 min lockout
- Audit immutability enforced in the database (REVOKE UPDATE/DELETE), not in application code; only the SECURITY DEFINER retention function may delete audit rows
- Retention is per-tenant (`tenants.retention_days`, default 365), driven by `python -m app.retention` (no scheduler infra in repo)
- VQ-403 offboarding: grace is validated **inside** the SECURITY DEFINER `purge_tenant()` SQL function — no API endpoint can purge early; purge runs only via `python -m app.offboard_purge`
- Offboarding requires password step-up: the acting super admin re-confirms with their own password (no MFA exists); wrong password → 403, generic detail
- The deletion report lives **outside** the tenant: `deletion_reports` table, no RLS, no `vaultiq_app` grant; it is the sole survivor of a purge (audit rows are purged with the tenant and the report supersedes them)
- Offboarding grace is a fixed 7 days (`OFFBOARD_GRACE_DAYS`); new state conflicts return 409 (VQ-107 used 400 — deliberate divergence, approved in APPROACH_VQ403.md)

## Tech Stack
- Backend: FastAPI (Python 3.11)
- Database: PostgreSQL 16 (Docker: vaultiq-db, port 5433)
- ORM: SQLAlchemy 2.0 (async)
- Migrations: Alembic
- Auth: PyJWT (VQ-105)
- CI: GitHub Actions (PostgreSQL service, alembic, pytest)
- Invite codes: `secrets.token_bytes(32)` → 43-char base64url, one-time, 7-day expiry
- Database access: app runs as `vaultiq` (dev superuser/BYPASSRLS); `vaultiq_app` role (NOBYPASSRLS) is the production app identity and is proven by RLS tests

## Database Tables
- tenants: id, short_code, name, status, storage_quota_mb, retention_days, timestamps
  - VQ-403 columns: offboarded_at, offboarded_by (FK users, ON DELETE SET NULL), purge_after, purged_at
- users: id, tenant_id (FK, nullable), email, password_hash, role, failed_login_attempts, locked_until, timestamps
- sessions: id, user_id (FK), tenant_id (FK), token_hash, is_revoked, expires_at, revoked_at, timestamps
- documents: id, tenant_id (FK), original_filename, stored_filename, mime_type, size_bytes, uploaded_by, created_at
- invites: id, tenant_id (FK), email, code, expires_at, used_at, created_by (FK users), created_at
- audit_logs: id, tenant_id (FK), actor_user_id (FK, nullable), actor_role, action, target_type, target_id, details (JSONB), created_at
- deletion_reports (VQ-403, platform-level): id, tenant_id (FK — tombstone tenant persists), short_code, name,
  initiated_by (FK users), initiated_at, purge_after, purged_at, grace_days, report (JSONB), backup_flag (JSONB), created_at

## RLS Policy
Every tenant-scoped table has FORCE ROW LEVEL SECURITY and a single policy:
`tenant_id = current_setting('app.current_tenant', true)::uuid`
- users, sessions, documents, invites, audit_logs
- Plus `invites` SELECT policy `invite_lookup_by_code` for invite acceptance
  (`app.invite_accept_code`)
- `documents` alone uses `current_setting('app.current_tenant'::text)` with no
  `missing_ok` argument — a query with the setting unset raises instead of
  returning no rows
- Known caveat: no policy has a `tenant_id IS NULL` branch for platform
  accounts — see Known Defects in `STATE.md`
- Index on audit export/purge path: `ix_audit_logs_tenant_created (tenant_id, created_at)`
- `deletion_reports` (VQ-403) deliberately has **no RLS** and no `vaultiq_app`
  grant: platform operators only (super_admin SELECT), stored outside the tenant
- `purge_tenant(uuid)` (VQ-403, SECURITY DEFINER): the only lawful delete path
  for a tenant's records including audit rows; validates grace internally
  (`status='offboarding' AND purge_after <= now()`) or RAISEs; guarded
  `to_regclass`+`tenant_id`-column loop purges derived tables when they exist

## Endpoints
### Auth
- POST /auth/login — Login with organisation_code, email, password → JWT token
- POST /auth/refresh — Refresh token (requires valid Bearer token)
- POST /auth/logout — Revoke session (requires valid Bearer token)
- GET /health — Health check (no auth required)

### Admin (super_admin only)
- POST /admin/tenants — Create tenant (short_code, name, storage_quota_mb, retention_days)
- GET /admin/tenants — List all tenants (no RLS filter)
- PATCH /admin/tenants/{id}/suspend — Suspend: status=suspended, revoke ALL sessions
- PATCH /admin/tenants/{id}/reactivate — Reactivate: status=active
- POST /admin/tenants/{id}/invite — Create one-time, time-limited invite for first Client Admin
- GET /admin/tenants/{id}/audit — Audit log for tenant

### Invite (public)
- POST /invite/accept — Accept invite (code, password) → creates client_admin, marks invite used

### Documents
- POST /documents — Upload file (multipart, validates mime/size)
- GET /documents — List documents (paginated, tenant-scoped)
- GET /documents/{id}/preview — Preview (text inline, 5000 chars)
- GET /documents/{id}/download — Download (original filename)
- DELETE /documents/{id} — Delete (file + DB)
- GET /documents/usage — Storage stats (count, bytes, MB)

### Audit (client_admin)
- GET /audit/export — Export own tenant's audit trail for a date range (csv|json);
  the export records itself (`export_audit`) before reading rows

### Offboarding & deletion reports (super_admin only, VQ-403)
- PATCH /admin/tenants/{id}/offboard — body {password}; step-up re-confirmation;
  status→offboarding, revokes ALL sessions, purge_after = +7 days (409 if already
  offboarding/purged, 404 unknown, allowed from active or suspended)
- PATCH /admin/tenants/{id}/cancel-offboarding — only from offboarding → active;
  clears offboard fields; audit `cancel_offboarding`
- GET /admin/deletion-reports — list platform deletion reports (newest first, limit 200)
- GET /admin/deletion-reports/{id} — single report (404 unknown)
- Purge itself has **no endpoint**: `python -m app.offboard_purge` (daily, same ops
  pattern as retention); grace unbreakable — enforced inside `purge_tenant()`

## Project Structure
> Reflects branch `vq-403` = main + VQ-403 (PR #17), with VQ-402 (PR #16) files
> marked `[VQ-402]` — they live on `vq-402`, not this branch, until merge.
> Branch-specific notes: `STATE.md`.

```
app/
  __init__.py
  config.py          — Settings (pydantic-settings)
  database.py        — Async SQLAlchemy engine, session, Base + set_tenant_context
  main.py            — FastAPI app with routers
  retention.py       — python -m app.retention — per-tenant audit/conversation purge [VQ-402]
  offboard_purge.py  — python -m app.offboard_purge — purge grace-expired offboarded tenants
  auth/
    __init__.py
    password.py      — bcrypt hash/verify + strength validation
    jwt.py           — create_access_token, decode_token (PyJWT)
    dependencies.py  — get_current_user, get_current_user_with_tenant
    permissions.py   — ROLE_MATRIX, require_roles()
  models/
    __init__.py
    base.py
    tenant.py        — Tenant model (incl. retention_days [VQ-402], VQ-403 offboard columns)
    user.py          — User model
    session.py       — Session model (token tracking, revocation, tenant_id)
    document.py      — Document model
    invite.py        — Invite model
    audit_log.py     — AuditLog model
    deletion_report.py — DeletionReport model (platform-level, no tenant scoping)
  routes/
    __init__.py
    auth.py          — Login, refresh, logout endpoints
    documents.py     — Document CRUD, preview, download, usage
    admin.py         — Tenant lifecycle (create/suspend/reactivate/invite/audit/offboard/
                       cancel-offboarding/deletion-reports) — super_admin only
    invite.py        — POST /invite/accept — public invite acceptance
    audit.py         — GET /audit/export — tenant audit trail export [VQ-402]
  schemas/
    __init__.py
    auth.py          — LoginRequest, TokenResponse, RefreshRequest, MessageResponse
    tenant.py        — TenantCreate, TenantResponse, TenantStatus,
                       TenantOffboardRequest, DeletionReportResponse
    user.py          — UserCreate, UserResponse
    document.py      — DocumentResponse, DocumentListResponse, StorageUsageResponse
  services/
    storage.py       — File save/delete with tenant isolation + purge_tenant_storage (VQ-403)
    audit.py         — write_audit_log — single fail-closed audit writer [VQ-402]
tests/
  __init__.py
  conftest.py        — DB fixtures (async engine, session, db_conn, app_db_conn,
                       app_db_engine, app_db_session, tenant_a/tenant_b, tokens)
  isolation_manifest.py   — Route manifest, single source of truth for VQ-110 coverage
  test_tenant.py     — 8 tests for VQ-101
  test_auth.py       — 18 tests for VQ-105
  test_tenant_context.py — 5 tests for VQ-103
  test_documents.py  — 18 tests for VQ-104/VQ-106
  test_rls.py        — 15 tests for VQ-102 (RLS isolation, roles, async ORM)
  test_permissions.py — 21 tests for VQ-106
  test_tenant_lifecycle.py — 21 tests for VQ-107
  test_isolation_suite.py — VQ-110 cross-tenant suite + route coverage guard
  test_audit_retention.py — 22 tests for VQ-402 [VQ-402]
  test_offboarding.py — 18 tests for VQ-403 (step-up, grace, purge must-prove, guards)
alembic/
  env.py
  versions/
    001_initial.py   — Tenants + Users + RLS migration
    002_add_sessions.py — Sessions table + lockout columns
    003_rls_hardening.py — FORCE RLS, vaultiq_app/vaultiq_super_admin roles
    d9ecec7d2e04_vq_104_add_documents_table_for_per_.py — Documents table + RLS
    a1340d9f596a_merge_vq_102_rls_hardening_and_vq_104_.py — Merge migration
    004_tenant_lifecycle.py — Invites, audit_logs, storage_quota_mb
    005_invite_code_lookup.py — Invite code RLS policy, audit actor_role text, tenants grant
    006_sessions_tenant_nullable.py — sessions.tenant_id nullable (super-admin sessions)
    007_audit_retention.py — VQ-402: retention_days, audit REVOKE, purge function, index [VQ-402]
    007_offboarding.py — VQ-403: offboard columns, deletion_reports, purge_tenant()
                         (NOTE: second head vs 007_audit_retention — re-parent/merge at integration)
.github/
  CHECKLIST.md       — Review checklist and common mistakes
  workflows/
    test.yml         — CI pipeline (PostgreSQL, alembic, pytest)
```

## CI Pipeline
**File:** `.github/workflows/test.yml`
- Triggers: pushes to feature branches, PRs to `main`
- Services: `pgvector/pgvector:pg16` on port 5432
- Steps: checkout → build image (libmagic/poppler/tesseract) → setup Python 3.11 → install deps → wait for PG → alembic upgrade head → create vaultiq_app role + grants → pytest tests/
- Known caveat: CI's pytest step connects as the `vaultiq` superuser — see Known Defects in `STATE.md`

## Tooling
- `winget install GitHub.cli` — **done**
- `gh auth login` — **done** (authenticated as intern142, HTTPS protocol)
- `gh repo view intern142/ChatBot_VaultIQ` — **done** (repo access verified)
