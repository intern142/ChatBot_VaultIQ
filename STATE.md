# VaultIQ — Project State (volatile)

> **This is the only project file sessions may edit.** Everything that changes
> as work progresses lives here: branch/task status, gate progress, test counts,
> blockers, known defects, sprint plans, story history, branch-specific notes.
> Durable rules and reference live in `AGENTS.md` — **never edit that file, and
> never move state into it.** Update this file at each meaningful step.

---

## 🚧 Resume Here — read this block first, update it before ending every session
> Purpose: any model (big-pickle, nemotron, …) continues exactly where the last
> session left. Contract: **update this block at every meaningful step**, not
> only at session end. Last updated: 8 Oct 2026 (big-pickle).

**Current branch: `vq-403`** — cut from `main` @ `161eb6f` **by the user's
explicit instruction** (I had proposed stacking from `vq-402`; user chose main).
Consequences (important, do not rediscover):
- **VQ-402's code is NOT on this branch**: no `app/services/audit.py`, no
  migration `007_audit_retention`, no `/audit/export`, no `app/retention.py`.
  Offboarding audit must use the audit helper as it exists on `main`
  (local to `app/routes/admin.py`, writes to `audit_logs` which DOES exist).
  When PR #16 merges, rebase and switch to `services/audit.py`.
- **Migration-head collision planned for:** this branch will add its own
  `007_*` (down_revision `006`) → conflicts with VQ-402's `007_audit_retention`
  at integration. Fix at rebase time: re-parent onto VQ-402's 007 if merged
  first, otherwise add a merge migration (see pattern
  `a1340d9f596a_merge_...`).
- Ticket dependency "Depends on: VQ-107 ✅, VQ-402 ⏳" — VQ-402 side handled by
  the integration plan above; flag it in the approach note.

**Next actions, in order:**
1. ~~Gate 1: `APPROACH_VQ403.md`~~ → approved by user ("continue gate 2").
2. ~~Gate 2: implementation~~ → done, commits on `vq-403`:
   - `bae1a6a` migration 007 (grace columns, deletion_reports, purge_tenant fn) + models/schemas
   - `e2c8d59` offboard/cancel endpoints + report read APIs + ROLE_MATRIX + manifest
   - `a6bbce7` purge CLI + storage wipe helper
   - `3f9c873` + `0652f49` tests (18 in `tests/test_offboarding.py`)
3. ~~Gate 3: tests green~~ → full suite **155 passed** (324s) on fresh
   `vaultiq_vq403` (migrations 001→007 + downgrade/upgrade roundtrip verified);
   CLI smoke test green (`%TEMP%\opencode\vq403_purge_smoke.py`).
4. ~~Gate 4: self-review~~ → `VQ403_SELF_REVIEW.md` written (all 5 ACs + both
   must-proves walked).
5. **~~Open PR~~ done → Gate 5 (human review) ⏳.** PR #17:
   https://github.com/intern142/ChatBot_VaultIQ/pull/17 (vq-403 → main).
   Post Gate 3/4 evidence there if asked.
6. Gate 6: live container verify — rebuild, uvicorn, exercise offboard →
   backdate → purge → report on live system, paste evidence on PR ⏳
7. Gate 7: Friday demo ⏳
8. VQ-402 leftovers (human-gated): Gate 5 review on PR #16, Gate 7 Friday demo.
   PR #16 and this branch both touch `AGENTS.md`/`STATE.md` — trivial conflicts
   at merge, resolve by keeping latest.
9. Optional hardening offered but not done: `opencode.json` `instructions`
   auto-loading this file.

**Never do:**
- Edit `AGENTS.md` (stable file — byte-identical for every model/branch).
- Commit the repo-root scratch debris: `debug_*.py`, `_g6_*.py`,
  `test_db_connection.py` (other stories' leftovers, untracked on purpose).
- Code before Gate 1 approval on a new story.
- Touch the stash `VQ-208 Gate 6 WIP` unless returning to that story.

**Environment facts:**
- Test DB for current story: **`vaultiq_vq403`** (port 5433,
  vaultiq/vaultiq_secret) — fresh DB, migrations 001→007 applied. Run tests with
  `DATABASE_URL` + `DATABASE_URL_SYNC` pointed at it (+ `PYTHONPATH` = repo root).
  Shared `vaultiq` DB is off-limits; `vaultiq_vq402` belongs to VQ-402's branch.
- Live-verify pattern: `uvicorn app.main:app --host 127.0.0.1 --port 8000`
  with those env vars; scratch scripts go in `%TEMP%\opencode`, not the repo.
- GH CLI authenticated as intern142; PR #16 = VQ-402, PR #17 = VQ-403.

---

## VQ-403 — Tenant offboarding and full purge (current story, spec already read)
> Source: `C:\Users\Test user 1\Documents\vq403.txt` (copied here so resume
> doesn't depend on the external file). Track BE · P0 · 5pt · 8–9 Oct 2026.
> **Depends on: VQ-107 ✅, VQ-402 ⏳ (PR #16).**

**Objective:** When a client leaves, nothing of theirs remains anywhere — and we can hand them a report proving it.

**Acceptance criteria:**
- Super Admin can offboard a tenant after re-confirming their own identity; the
  tenant is locked immediately and all its sessions end
- A 7-day grace period during which the offboarding can be cancelled
- After the grace period, everything belonging to the tenant is removed: every
  record, every derived search artefact, every file, every cached answer, every
  pending job, and its index space
- Backups containing the tenant are flagged so they expire per policy
- A deletion report — what was removed, how much, when, by whom — is produced
  and stored outside the tenant

**Must be proven:**
- Automated test: after purge, zero records and zero files reference the tenant,
  and other tenants are untouched
- Evidence from staging: a purged test tenant, database and disk searched for
  its identity, and the deletion report

**Open design questions for APPROACH_VQ403.md (decide there, don't guess silently):**
- Purge targets mostly don't exist on `main` yet (chunks, embeddings,
  conversations, cached answers, jobs) → `to_regclass`-guard pattern like
  VQ-402; real targets that DO exist: users, sessions, invites, documents,
  audit rows, `storage/{tenant_id}/**` on disk.
- `offboarding` status exists in the schema (VQ-101) but no endpoint drives it;
  grace period needs a state machine + `offboarded_at`/deadline column.
- "Re-confirm identity" = password re-entry for super admin (no MFA exists).
- Deletion report location: platform-level table (no `tenant_id`,
  super_admin only) so it survives the purge and stays outside the tenant.
- "Backups flagged": no backup infra in repo — decide durable flag/record
  semantics in the approach note.
- Offboarding + purge must be audited via `write_audit_log` (VQ-402).

---

## Project State
- Current branch: **`vq-403`** (cut from `main` @ `161eb6f` by user instruction;
  see Resume Here for VQ-402 integration plan)
- Current task: **VQ-403** — Tenant offboarding and full purge
  (Gates 1–4 ✅ · PR #17 open: https://github.com/intern142/ChatBot_VaultIQ/pull/17
  · Gate 5 review + Gate 6 live verify + Gate 7 demo ⏳)
- Test suite on `vq-403`: **155 passed** on DB `vaultiq_vq403` (this branch's suite)
- Previous story: **VQ-402** — Audit/export/retention, PR #16 open (Gates 1-4, 6 ✅;
  Gate 5 review + Gate 7 demo pending), branch `vq-402`
- Test suite on `vq-402`: **163 passed** (`python -m pytest tests/ -q`, 326s) on DB `vaultiq_vq402`
- Test suite on main: **137 passed** (`python -m pytest tests/ -q`, 232s) — as of `19ea79f` (VQ-110 merged)
- Test suite on `vq-201-tenant-upload` (PR #10, not merged): 163 tests (upload/OCR/quota)
- Both main and branch runs connect as the `vaultiq` superuser, so neither exercises RLS
- Sprint 1 + Sprint 2 merged to main: VQ-101, 102, 103, 104, 105, 106, 107, 110
- VQ-201 work is stashed: `git stash list` → `VQ-208 Gate 6 WIP` (restore when returning)
- **Migration-head risk:** VQ-402 adds `007_audit_retention` (down_revision 006); the
  `vq-201-tenant-upload` branch also adds migrations descending from 006. Merging both
  creates two alembic heads — a merge migration will be needed at that point.

## VQ-402 — Audit trail, compliance export, retention (current)
**Branch:** `vq-402` · **PR:** #16 · **Test DB:** `vaultiq_vq402` (port 5433) — dedicated DB,
migrations 001→007, shared `vaultiq` DB left untouched.

**Gates:** 1 ✅ (`APPROACH_VQ402.md`) · 2 ✅ · 3 ✅ (163 passed) · 4 ✅ (`VQ402_SELF_REVIEW.md`) ·
5 ⏳ (PR #16) · 6 ✅ (evidence in PR comment) · 7 ⏳ (Friday demo)

**Gate 6 evidence (PR #16 comment):**
- 10 actions on live uvicorn → export contains all 10 + `export_audit`
- `vaultiq_app` direct connection: UPDATE/DELETE denied (`42501`), RLS 0 rows without
  context / 12 with; INSERT allowed (by design); owner (`vaultiq`) path only for retention
- `python -m app.retention` iterates POLA/POLB/VQ402LIVE, each with own `days=365`

**What exists:**
- `app/services/audit.py` — single fail-closed writer; wired into login, logout, failed_login
  (4 reasons), create_invite, accept_invite, upload_document, delete_document, create_tenant
  (retention_days in details), suspend_tenant, reactivate_tenant, export_audit
- Reserved action names (features not on `main` yet, see `APPROACH_VQ402.md`): `role_change`
  (VQ-301), approve/reject (VQ-204), question+docs+confidence (VQ-210), `settings_change`
- Migration `007_audit_retention.py` — `tenants.retention_days` (CHECK >=1),
  REVOKE UPDATE/DELETE on `audit_logs` from `vaultiq_app` + `vaultiq_super_admin`,
  SECURITY DEFINER `vaultiq_purge_tenant_retention(tenant)` (EXECUTE revoked from PUBLIC),
  index `ix_audit_logs_tenant_created`; downgrade → upgrade roundtrip verified
- `GET /audit/export` — client_admin only, tenant from token, date range, csv/json,
  self-records (`export_audit`) before reading rows
- `app/retention.py` — `python -m app.retention` CLI, per-tenant purge; cron `0 3 * * *`
  documented (no scheduler infra in repo)
- Guards updated: manifest + coverage guard cover `/audit/export`; `PERMISSIONS.md` row 5
- Tests: `tests/test_audit_retention.py` (22) + 4 isolation-suite export tests = +26

**Caveat:** live uvicorn ran as `vaultiq` superuser (Known Defect #1); RLS/immutability
proven via separate direct `vaultiq_app` connections (Known Defects #1/#2 out of scope).

## Known Defects (must be fixed before VQ-202)
1. **The test suite (and CI) run as `vaultiq`, which is `rolsuper = t, rolbypassrls = t`.** Every
   RLS policy is inert during test and CI runs. VQ-102's claim that "the database itself
   refuses cross-tenant reads" is therefore only proven by the handful of tests that use
   the `app_db_session` / `app_db_conn` fixtures — never through the HTTP endpoints.
   CI sets `DATABASE_URL` with `vaultiq` credentials; the fix is to split identities:
   seed/migrate as superuser, run the application under test as `vaultiq_app`.
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

## Blockers
- NONE — Windows asyncpg flakes resolved (Selector event loop policy + session-scoped event loop fixture)

---

## Sprint 1 Progress
- [x] VQ-101 — Tenant data model (Gates 1-4, 6 complete; Gate 5 pending)
- [x] VQ-105 — Tenant-scoped login and session tokens (Gates 1-4, 6 complete; Gate 5 pending)
- [x] VQ-103 — Tenant context on every request (Gates 1-4, 6 complete; Gate 5 pending)
- [x] VQ-104 — Per-tenant document storage (Gates 1-4, 6 complete; Gate 5 pending)

```
Sprint 1: VQ-101 ✅ → VQ-105 ✅ → VQ-103 ✅ → VQ-104 ✅
Sprint 2: VQ-102 ✅ → VQ-106 ✅ → VQ-107 ✅ → VQ-110 ✅
Sprint 3: VQ-201 → VQ-202 → VQ-203 → VQ-204
Sprint 4: VQ-402 (current) → VQ-403
```

## Sprint 2 / Week 2 Plan (21–25 Sep)

**Objective:** Database itself refuses cross-tenant reads — even if code has bugs. Roles enforced everywhere. Automated test proves A can't touch B. Can create/suspend customers.

**Tasks (Asana order: 102 → 106 → 107 → 110):**
| Task | Description | Depends On | Status |
|------|-------------|------------|--------|
| VQ-102 | Database-level tenant isolation — RLS policies on all tenant-scoped tables, automated cross-tenant read test, role enforcement | VQ-101, VQ-103 | **Gates 1-4, 6 ✅ (ACs 4 & 6 open, see below)** |
| VQ-106 | Role and permission model — permissions matrix, decorator enforcement, Super Admin denied on content | VQ-105 | **Gates 1-6 ✅** |
| VQ-107 | Tenant lifecycle — create, suspend/reactivate, invite first Client Admin, audit trail | VQ-105, VQ-106 | **Gates 1-7 ✅, evidence caveat (see below)** |
| VQ-110 | Cross-tenant isolation test suite v1 — automated proof that tenant A cannot touch tenant B through any operation | VQ-102, VQ-106 | Merged to main. Gates 1-4 code complete; **Gate 3 + Gate 6 evidence being re-verified** (see Known Defects) |

**Must Be True by Friday (Sprint 2):**
- RLS policies on ALL tenant-scoped tables (users, documents, sessions, future tables)
- Automated test: Tenant A cannot read, update, delete Tenant B rows via ANY query path
- Application DB role cannot bypass RLS (no BYPASSRLS)
- No-tenant session returns zero rows
- Latency within 10% of Sprint 0 baseline
- Permissions matrix documented, uniform enforcement, Super Admin denied on content
- Create/suspend/invite tenant flow works end-to-end
- Isolation test suite covers every operation, blocks merge on failure

### VQ-102 — Database-level tenant isolation [BE][W2][P0][8pt] — **Gates 1-4, 6 ✅ (ACs 4 & 6 open)**
**Depends on:** VQ-101, VQ-103
**Objective:** Even if application code has a bug, the database itself must refuse to return, change or delete one tenant's data to a session acting for another tenant.

> **Evidence caveat:** the 15 RLS tests in `test_rls.py` are the only tests that
> connect as `vaultiq_app`, and they exercise the ORM/SQL layer directly rather
> than the HTTP endpoints. So VQ-102's core claim — that the *database* refuses
> cross-tenant access — is proven at the query layer but **not yet proven through
> the application request paths**, because the suite runs as the RLS superuser
> everywhere else. See Known Defects.

**Completed:**
- Gate 1: Approach note drafted — policy design, tenant context via SET LOCAL, DB roles (vaultiq_app, vaultiq_super_admin), connection pool implications
- Gate 2: Implementation — Migration 003_rls_hardening.py with FORCE RLS on users, sessions tables; tenant_id column added to sessions; dedicated roles created with NOBYPASSRLS; grants configured
- Gate 3: Tests written and green — 15 tests covering: cross-tenant read/update/delete blocked for users & sessions; no-tenant context returns zero rows; vaultiq_app role cannot bypass RLS; vaultiq_super_admin limited grants; async ORM tests with vaultiq_app role
- All 23 tests passing (8 tenant + 15 RLS)
- Gate 4: Self-review checklist — acceptance criteria walked, checklist ticked, PR #6 opened
- Gate 5: Pending (reviewer approval)
- **Gate 6: Live container verified** — 23/23 tests pass, cross-tenant isolation proven via psql
  - `vaultiq_app` with EVIDENCE_A context → sees only `admin@tenantA.com` (1 row)
  - `vaultiq_app` querying `admin@tenantB.com` with A context → 0 rows (RLS blocks)
  - `vaultiq_app` no tenant context → 0 rows
  - `vaultiq_super_admin` → CAN read tenants, CANNOT read users/sessions (permission denied)
  - `rolbypassrls = f` for both vaultiq_app and vaultiq_super_admin

**Acceptance Criteria Status:**
1. ✅ Every table holding client data protected at DB level (users, sessions FORCE RLS)
2. ✅ Application account (vaultiq_app) cannot bypass protection (NOBYPASSRLS)
3. ✅ No-tenant session returns zero rows (tested)
4. ⏳ Background jobs bound to one tenant (pending implementation)
5. ✅ Super Admin reads use separate limited DB identity (vaultiq_super_admin with grants only on tenants)
6. ⏳ Latency within 10% baseline (pending measurement)

### VQ-106 — Role and permission model [BE][W2][P0][5pt] — **Gates 1-6 ✅**
**Depends on:** VQ-105
**Branch:** `vq-106-permissions` · **PR:** #7
**Objective:** Three roles — Super Admin, Client Admin, Employee — with a written, enforced matrix of what each may do, so that nothing can be added to the system without declaring who may call it.

**Completed:**
- Gate 1: Approach note — permissions matrix, `require_roles()` decorator design (commit bf760be)
- Gate 2: Implementation — `app/auth/permissions.py` with `ROLE_MATRIX`, `require_roles()`, `require_roles_with_tenant()`; role checks on all endpoints (commit a074126)
- Gate 3: 21 permission tests — router walk (3), denied-role (8), allowed-role (10); 44 total tests passing (commit 224f4ac)
- Gate 4: Self-review — all 5 acceptance criteria confirmed, PR #7 opened
- **Gate 6: Live container verified** — permission enforcement matrix proven on running container

**Gate 6 Evidence — Live Container Status Codes:**

| Endpoint | client_admin | employee | super_admin |
|----------|-------------|----------|-------------|
| GET /documents | 200 | 200 | **403** |
| GET /documents/usage | 200 | **403** | **403** |
| GET /documents/{id}/preview | 404* | 404* | **403** |
| GET /documents/{id}/download | 404* | 404* | **403** |
| DELETE /documents/{id} | **403** | **403** | **403** |
| POST /auth/logout | 200 | 200 | 200 |

*404 = document not found (permission allowed); **403** = explicitly denied by permission matrix

**Key Result:** Super Admin explicitly denied on ALL `/documents/*` endpoints — 403 returned for every document operation. Employee limited to list/preview/download. Client Admin has full access.

**Acceptance Criteria Status:**
1. ✅ Permissions document lists every operation (`PERMISSIONS.md`, `ROLE_MATRIX`)
2. ✅ Enforcement is uniform (`require_roles()` dependency factory)
3. ✅ Router walk test catches un-annotated endpoints
4. ✅ Super Admin denied on all `/documents/*` (6 denied-role tests + live container)
5. ✅ Employees limited to list/preview/download

**Pending:** Gate 5 (code review), Gate 7 (demo)

### VQ-107 — Tenant lifecycle: create, suspend, reactivate, invite first admin [BE][W2][P0][5pt] — **ALL GATES ✅ (1-7)**
**Depends on:** VQ-105, VQ-106
**Branch:** `vq-107-tenant-lifecycle` · **PR:** #8 (merged)
**Note:** Tracked as Sprint 3 in Asana but Sprint 2 here per our plan.
**Objective:** The platform operator can bring a new client organisation onto VaultIQ, pause it, and resume it, without touching the database by hand — and without needing internet or email.

> **Evidence caveat:** the Gate 6 run exercised the full create → invite →
> accept → suspend → refused sequence, but as the `vaultiq` superuser, so the
> RLS policies on `users`/`sessions`/`invites` were inert. The sequence itself
> is genuine; it has not yet been shown to hold with the policies enforced.
> The super-admin identity is additionally broken under `vaultiq_app` — see
> Known Defects.

**Completed:**
- Gate 1: Approach note — `APPROACH_VQ107.md` (endpoints, invite code design, suspend semantics, risks)
- Gate 2: Implementation complete (commit 1b5971a, then Gate 2/3 fixes)
  - Migration 004 + 005 — invites & audit_logs tables (FORCE RLS), storage_quota_mb, actor_role as text, invite code-lookup RLS policy (`app.invite_accept_code`), tenants SELECT grant for vaultiq_app
  - Admin router `app/routes/admin.py` — POST/GET /admin/tenants, suspend, reactivate, invite, audit (super_admin only)
  - Public `POST /invite/accept` in `app/routes/invite.py` — creates first Client Admin, one-time / time-limited
  - Admin endpoints set tenant context (`set_tenant_context`) so writes pass FORCE RLS under vaultiq_app too
  - Tenant short_code format validation (2-20 uppercase alnum) + 409 on duplicate
  - audit_logs actor_role now VARCHAR(50) — accept_invite writes actor_role='system' (not in user_role enum)
- Gate 3: Written and green — `tests/test_tenant_lifecycle.py`, 21 tests. Full suite **65 passed**. Covers: create/duplicate/format, invite accept + login, one-time reuse, expiry, suspend revokes sessions in one request, reactivate, state machine, audit trail, permission denial on /admin, RLS invite isolation (tenant context vs code lookup vs insert blocked without context).
- Gate 4: Self-review — all 5 acceptance criteria walked and confirmed (`VQ107_SELF_REVIEW.md`), PR #8 opened
- **Gate 6: Live container verified** — full sequence proven on the running system (`uvicorn app.main:app` on 127.0.0.1:8000, Docker PG 5433)
- Gate 7: Demo ✅

**Gate 6 Evidence — Live Container Sequence:**
1. `POST /auth/login` SUPER → `role=super_admin`, `tenant_id=null`
2. `POST /admin/tenants` (OMEGA, 2048MB) → `201 status=active`
3. `POST /admin/tenants/{id}/invite` → 43-char code, `expires_at` +7 days
4. `POST /invite/accept` → `"Invite accepted successfully", tenant_id=<OMEGA>, user_id=<...>`
5. `POST /auth/login` OMEGA → `role=client_admin`
6. `PATCH /admin/tenants/{id}/suspend` → `status=suspended`
7. Pre-suspend client-admin token → **401** on next request
8. Fresh login while suspended → **403**
9. Re-accept of used invite → **400**
10. `PATCH /admin/tenants/{id}/reactivate` → `status=active`; login → **200**
11. `GET /admin/tenants/{id}/audit` → `reactivate_tenant[super_admin] -> suspend_tenant[super_admin] -> accept_invite[system] -> create_invite[super_admin] -> create_tenant[super_admin]`

**Acceptance Criteria:**
1. Create a tenant with code, name and storage quota
2. Suspend: every active session of that tenant stops working immediately and logins are refused; reactivate reverses it
3. Invite the first Client Admin: the system produces a one-time, time-limited invite the operator can hand over on screen; if an internal mail relay is configured it may also be sent
4. Accepting the invite lets the person set a password and become that tenant's Client Admin
5. Every action is recorded in the audit trail with who did it

**Approach Note Summary (APPROACH_VQ107.md):**
- Migration 004: `storage_quota_mb` on tenants; `invites` + `audit_logs` tables (FORCE RLS)
- Admin router (`/admin`, super_admin only): create, list, suspend, reactivate, invite, audit
- Public `POST /invite/accept` — creates user as client_admin
- Invite code: 32 bytes → 43-char base64url, one-time, default 168h, tied to tenant+email
- Suspend: status=suspended + revoke ALL sessions; login checks status in (suspended, offboarding) → 403
- Every admin action writes to audit_logs with actor, action, target, details

---

## Sprint 3 / Week 3 Plan (28 Sep – 2 Oct)

### VQ-201 — Document upload, tenant-scoped, with quota [BE][W3][P0][3pt] — **Gates 1-4 ✅, Gate 6 INVALID**
**Depends on:** VQ-104, VQ-106
**Objective:** A Client Admin can upload their organisation's documents in the formats HeXta already supports, and those documents land in that organisation's own store.

> ⚠️ **Gate 6 evidence previously recorded was wrong and has been withdrawn.**
> It claimed "163/163 tests passed with `vaultiq_app` role, `BYPASSRLS=false`".
> The suite runs as `vaultiq`, which is `rolsuper = t, rolbypassrls = t`, so RLS
> was inert for every one of those 163 tests. The `vaultiq_app` role is created
> and granted in CI but the app never connects as it. Gate 6 must be re-run.
> This story cannot be signed off until it is.

**Completed:**
- Content-based MIME detection (libmagic + OLE/OOXML/ODF/EPUB/EML signatures)
- 19 allowed MIME types covering all HeXta formats + scanned PDF/images via OCR
- Bounded offline OCR (tesseract + poppler) with timeouts, page/text caps, semaphore
- Category enum per upload (policy/hr/sop/process/other)
- Per-file (50MB) + per-tenant quota enforcement with advisory lock, pre-save check
- Role restriction: client_admin only for POST /documents
- Extraction metadata persisted (text, method, status, pages, truncated)
- RLS policies written for the app-role (`vaultiq_app`, NOBYPASSRLS) — **but never actually exercised; see Known Defects**
- Docker image with offline runtime (libmagic, poppler, tesseract, olefile)
- CI updated with OCR_REQUIRED=true, internal network verification
- Full test suite: 163 tests passing (216s) — **as the RLS superuser**

**Gate 6 Evidence — Live Container (WITHDRAWN, to be re-run):**
- ~~163/163 tests passed with `vaultiq_app` role, `BYPASSRLS=false`~~ — **not true; the run used the `vaultiq` superuser**
- All 19 formats accepted; PHP MIME rejected (this part was observed and stands)
- Quota/RLS/role checks verified — quota and role yes; RLS untested under enforcement
- OCR completed for scanned PDF/PNG/JPEG/TIFF; non-OCR formats report `not_required` (stands)

**Acceptance Criteria Status:**
1. ✅ All 19 formats + OCR path work
2. ✅ Category recorded per upload
3. ✅ Quota enforced before persistent write; clear error messages
4. ✅ File type judged from content (libmagic + signature detection)
5. ✅ Employees blocked (403)

**Pending:** Gate 5 (code review), Gate 6 (re-run under `vaultiq_app`), Gate 7 (demo)
**Branch adds:** `app/services/ocr.py`, `app/services/file_detection.py`, migrations 007/008 (see migration-head risk in Project State)
**Debris on the VQ-201 branch (not on main — remove before merging PR #10):**
- `commit_msg.txt` — an accidentally committed commit-message scratch file. It is
  also where the super-admin RLS bug got noted and then buried.
- `test_health.py` — debug script at repo root, hardcoded to port 8001, gets
  collected by pytest.

---

## Merged Story Records

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
- `tests/isolation_manifest.py` — route manifest (single source of truth) for VQ-110 coverage

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
- Gate 4: Review checklist added, PR opened (commit 08e40a6)
- Gate 5: Pending (reviewer approval)
- **Gate 6: Live container verified** — 26/26 tests pass against Docker PostgreSQL, health endpoint responds, login endpoint responds
- **Gate 6 Evidence — JWT Claims from live container logins:**
  - **Super Admin** (org_code=SUPER): `sub=<user_id>`, `role=super_admin`, `tenant_id=null`, `jti=<session_id>`, `exp=24h`
  - **Client Admin** (org_code=ACME): `sub=<user_id>`, `role=client_admin`, `tenant_id=d3985764-1cd6-4c25-baea-e73cefcc9fd6`, `jti=<session_id>`, `exp=24h`
  - **Employee** (org_code=ACME): `sub=<user_id>`, `role=employee`, `tenant_id=d3985764-1cd6-4c25-baea-e73cefcc9fd6`, `jti=<session_id>`, `exp=24h`

### VQ-103 — Tenant context on every request ✅
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

### VQ-104 — Per-tenant document storage ✅
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

---

## Story Specs (from Asana — requirement records, not status)

### VQ-103 — Tenant context on every request (Detailed)
**Note:** This is **VQ-103**, not HX-103. Asana shows it as HX-103 but we are not using HX in this application. The correct story ID is **VQ-103**.
**[BE][W1][P0][3pt]**

**Objective:** Exactly one place in the system decides which tenant a request belongs to, and it cannot be influenced by anything the caller sends other than a valid session token.

**Acceptance Criteria:**
1. The tenant for a request comes **only** from the verified session token
2. Any tenant identifier supplied elsewhere in the request is **not trusted**; the request is rejected or the value ignored (document which)
3. A request for a resource that belongs to another tenant is refused **without revealing** that the resource or the other tenant exists
4. Users of a **suspended or offboarding tenant** are refused on every operation except logout
5. Business logic **never has to parse the token** itself

**Must Be Proven:** Automated tests: tampered token, cross-tenant resource, injected tenant id, suspended tenant · Evidence from the live container

**Gates:**
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

### VQ-101 — Tenant data model and migration (Detailed)
**Note:** This is **VQ-101**, not HX-101. Asana shows it as HX-101 but we are not using HX in this application. The correct story ID is **VQ-101**.
**[BE][W1][P0][5pt]**

**Objective:** Introduce the client organisation (tenant) as a first-class concept so that every piece of data in VaultIQ belongs to exactly one tenant.

**Acceptance Criteria:**
1. A tenant can be created with a unique short code, a display name and a status (active / suspended / offboarding / purged)
2. Every record that holds client data (users, documents and their versions, text chunks, embeddings, conversations, messages, feedback, audit entries, sessions, cached answers, ingestion jobs) is linked to one tenant and cannot exist without one
3. Platform (Super Admin) accounts are the only accounts not linked to a tenant
4. All existing HeXta/ADS data ends up under one tenant with nothing lost
5. The change can be rolled back

**Must Be Proven:** Before/after record counts for the ADS migration, posted as a comment · An automated test that inserting client data without a tenant fails · The full existing test suite still passes

**Out of Scope:** Enforcing who can read which tenant's data (VQ-102, VQ-103)

**Gates:**
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

### VQ-105 — Tenant-scoped login and session tokens (Detailed)
**Note:** This is **VQ-105**, not HX-105. Asana shows it as HX-105 but we are not using HX in this application. The correct story ID is **VQ-105**.
**[BE][W1][P0][5pt]**

**Objective:** Users log in to their own organisation, and every request afterwards carries proof of who they are, their role, and which tenant they belong to.

**Acceptance Criteria:**
1. Login requires the organisation code, email and password
2. A wrong organisation code, wrong email and wrong password all produce the same response, in the same time, so an attacker cannot tell which one was wrong
3. The session token identifies the user, their role and their tenant; a platform (Super Admin) token has no tenant
4. Sessions can be refreshed and revoked; a revoked session stops working on the very next request
5. Repeated failed logins lock the account temporarily
6. Minimum password strength is enforced

**Must Be Proven:** Automated tests for the full success/failure matrix, a tampered token, and a revoked session · Evidence from the live container showing decoded tokens for each role (secrets redacted)

**Out of Scope:** Invite and password-reset flows (VQ-107, VQ-301)

**Gates:**
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

### VQ-104 — Per-tenant document storage (Detailed)
**Note:** This is **VQ-104**, not HX-104. Asana shows it as HX-104 but we are not using HX in this application. The correct story ID is **VQ-104**.
**[BE][W1][P0][3pt]**

**Objective:** Each tenant's uploaded files are kept physically separate, and no user-supplied value can influence where a file is stored or which file is read.

**Acceptance Criteria:**
1. Files are stored in a location derived from the tenant and a server-generated document identity, never from the uploaded filename
2. Reading, previewing or downloading a file re-checks that the file belongs to the requesting tenant
3. Per-tenant storage usage is tracked so quotas can be enforced later

**Must Be Proven:** Automated tests for path-manipulation attempts and for cross-tenant download · Evidence from the live container showing where an uploaded file landed and a refused cross-tenant fetch

**Gates:**
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

### VQ-107 — Tenant lifecycle (Detailed)
**Note:** This is **VQ-107**, not HX-107. Asana shows it as HX-107 but we are not using HX in this application. The correct story ID is **VQ-107**.
**[BE][W2][P0][5pt]**

**Objective:** The platform operator can bring a new client organisation onto VaultIQ, pause it, and resume it, without touching the database by hand — and without needing internet or email.

**Acceptance Criteria:**
1. Create a tenant with code, name and storage quota
2. Suspend: every active session of that tenant stops working immediately and logins are refused; reactivate reverses it
3. Invite the first Client Admin: the system produces a one-time, time-limited invite the operator can hand over on screen; if an internal mail relay is configured it may also be sent
4. Accepting the invite lets the person set a password and become that tenant's Client Admin
5. Every action is recorded in the audit trail with who did it

**Must Be Proven:** Automated tests: invite cannot be reused or used after expiry; suspend takes effect within one request; tenant code uniqueness and format · Evidence from the live container of the full create → invite → accept → suspend → refused sequence

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

### VQ-110 — Cross-tenant isolation test suite v1 (Detailed)
**Note:** This is **VQ-110**, not HX-110. Asana shows it as HX-110 but we are not using HX in this application. The correct story ID is **VQ-110**.
**[BE][W2][P0][5pt]**

**Objective:** A permanent, automated proof that tenant A cannot touch tenant B through any operation the system exposes — and that stays true as new operations are added.

**Acceptance Criteria:**
1. Two fully populated test tenants (admins, employees, documents, conversations, feedback)
2. Every operation the system exposes is exercised with tenant A's credentials against tenant B's identifiers
3. The expected outcome is refusal; the response must never contain any tenant B identifier or content
4. Adding a new operation without covering it in the suite causes the suite to fail
5. The suite runs on every pull request and blocks merging

**Must Be Proven:** A coverage report showing every operation exercised · A demonstration: break isolation on a throwaway branch and show the suite catching it

**Gates:**
| Gate | Requirement |
|------|-------------|
| 1 | Approach note — fixture design, route discovery, how resource ids map per route. Reviewer approves first. |
| 2 | Implement — Branch `vq-110-isolation-suite-v1`. |
| 3 | Tests written and green — Suite covers every route; coverage report attached; CI blocks merge on failure. |
| 4 | Self-review checklist — Confirm body is checked, not only status. Tick Common mistakes. Open PR. |
| 5 | Code review — Lead reviews. |
| 6 | Live container verify — Run the suite against the live container, not only the test DB. Paste the run. |
| 7 | Demo & sign-off — Friday evening. |
