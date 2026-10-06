# VaultIQ Backend — AGENTS_BE.md (BE_accurate state)

## VaultIQ SOP — How We Work
**Build window:** 9 Sep – 8 Oct 2026 | **Shift:** 13:30 – 22:30
**Role:** Backend (Chaithanya) — Database, tenant isolation, login/permissions, document processing, search, answer selection, audit, offboarding

### Four Rules That Never Bend
1. **Tenant isolation is absolute** — Tenant A can never read/retrieve/list/search/cache-hit/infer anything from Tenant B
2. **No internet** — Zero outbound network access in deployed stack
3. **No LLM, no generated text** — Answers are extracted sentences from customer docs only
4. **Platform operators see no customer content** — Super Admin sees counts/storage/health/usage only

### Seven Gates (must tick in order)
| Gate | Name | Requirement |
|------|------|-------------|
| 1 | Approach note | Post plan, wait for approval before coding |
| 2 | Implement | Small commits, story ID in every message, push daily |
| 3 | Tests green | Paste actual command + output. Existing suite must stay green |
| 4 | Self-review | Walk acceptance criteria one by one, confirm each, then open PR |
| 5 | Code review | Lead reviews (never other intern) |
| 6 | Live container verify | Rebuild, run, exercise, paste what you did + what came back |
| 7 | Demo & sign-off | Friday evening. Not demoed = not done |

---

## Project State — BE_accurate branch (as of 30 Sep 2026)
- **Current branch:** `BE_accurate` (tracking `origin/BE_accurate`, up to date)
- **Current HEAD:** `d90833d` — "Enable CORS for the frontend dev server"
- **Base:** Sprint 1 + Sprint 2 fully merged (commit `9e5ecc8`)
- **Test suite on BE_accurate:** **145 passed** (`python -m pytest tests/ -q`, ~264s)

### Completed on BE_accurate (Sprint 1 + 2, all Gates 1-4, 6 ✅)

| Task | Description | Tests | Key Evidence |
|------|-------------|-------|--------------|
| VQ-101 | Tenant data model + migration (RLS on users) | 8 | Migration up/down, 8/8 pass |
| VQ-105 | Tenant-scoped login/JWT, lockout, refresh/revocation | 18+8=26 | Live JWT claims for all 3 roles |
| VQ-103 | Tenant context middleware — token-only source | 5 | Tampered/cross-tenant/suspended blocked |
| VQ-104 | Per-tenant document storage, quota tracking | 13+5=18 | Cross-tenant 404, path traversal blocked |
| VQ-102 | DB-level isolation — FORCE RLS, `vaultiq_app` NOBYPASSRLS | 15 | psql: A context sees 1, B sees 0 |
| VQ-106 | Role matrix — super_admin denied ALL /documents/* | 21 | Live: super_admin 403 on every doc op |
| VQ-107 | Tenant lifecycle — create/suspend/reactivate/invite/audit | 21 | Live full sequence: create→invite→accept→suspend→403 |
| VQ-110 | Cross-tenant isolation suite v1 — coverage guard | 137 | 36/36 live, route manifest guard proven |

### Separate branches (work done, not merged to BE_accurate)

| Branch | Task | Status | Notes |
|--------|------|--------|-------|
| `vq-201-tenant-upload` | VQ-201 Document upload — 19 formats + OCR, category, quota | Gates 1-4 ✅, Gate 6 evidence withdrawn | PR #10 open; 163 tests on branch; ran as `vaultiq` superuser so RLS inert |
| `vq-202-approval-versioning` | VQ-202 Approval & versioning — state machine, atomic swap | Gates 1-4 in progress | Branch exists; depends on 007 for platform writes |
| `vq-203` | VQ-203 Processing & indexing — worker fair scheduling, pgvector | Gates 1-4 in progress | Branch exists; worker blindness fix in progress |
| `vq-301-password-reset` | VQ-301 Password reset flow | Gate 1 ✅, Gate 2 partial | Fixture RLS visibility issues |

---

## Known Defects (must fix before VQ-202 / demo sign-off)

1. **Test suite runs as `vaultiq` (ROL BYPASSRLS)** — All 145 tests connect as the RLS superuser. Every RLS policy is inert during test/CI runs. The claim "database refuses cross-tenant reads" is proven only by the 15 `test_rls.py` tests that connect as `vaultiq_app` — not through HTTP endpoints. **Fix:** CI must seed as superuser, run tests as `vaultiq_app`.

2. **Super Admin auth broken under `vaultiq_app`** — `POST /auth/login` with `organisation_code=SUPER` returns **401**. RLS policies on `users`/`sessions` have no `tenant_id IS NULL` branch. Inserting a super-admin session → `InsufficientPrivilegeError`. Super Admin is the only role that can create a tenant, so this blocks VQ-202 live evidence. **Fix:** Migration 007 adding permissive `platform_rows` policies with `app.is_platform` gate.

3. **CORS commit `d90833d` has no story ID** — Gate 4 will flag. Needs ID from lead.

---

## Tech Stack
- Backend: FastAPI (Python 3.11)
- Database: PostgreSQL 16 (Docker: `vaultiq-db`, port 5433)
- ORM: SQLAlchemy 2.0 (async)
- Migrations: Alembic
- Auth: PyJWT
- CI: GitHub Actions (PostgreSQL service, alembic, pytest)
- Database roles: `vaultiq` (dev superuser/BYPASSRLS), `vaultiq_app` (NOBYPASSRLS, production identity)

---

## Key Endpoints on BE_accurate

| Category | Endpoints |
|----------|-----------|
| Auth | `POST /auth/login`, `/auth/refresh`, `/auth/logout` |
| Documents | `POST/GET/DELETE /documents`, `GET /documents/{id}/preview`, `/download`, `/usage` |
| Admin (super_admin) | `POST/GET /admin/tenants`, `PATCH /admin/tenants/{id}/suspend`, `PATCH .../reactivate`, `POST .../invite`, `GET .../audit` |
| Public | `POST /invite/accept`, `GET /health` |

---
## Database Tables
- `tenants`, `users`, `sessions`, `documents`, `invites`, `audit_logs`
- RLS (`FORCE ROW LEVEL SECURITY`) on all tenant-scoped tables
- Policy: `tenant_id = current_setting('app.current_tenant', true)::uuid`
- **Missing:** `tenant_id IS NULL` branch for platform accounts (defect #2)

---

## Sprint Progress
```
Sprint 1: VQ-101 ✅ → VQ-105 ✅ → VQ-103 ✅ → VQ-104 ✅
Sprint 2: VQ-102 ✅ → VQ-106 ✅ → VQ-107 ✅ → VQ-110 ✅
Sprint 3: VQ-201 (branch) → VQ-202 (branch) → VQ-203 (branch) → VQ-301 (branch)
```

---

## Frontend Branches (colleague's work)
| Branch | Base | Status |
|--------|------|--------|
| `be_clone` | `BE_accurate` (`d90833d`) | ✅ Has CORS, correct backend |
| `fe_clone` | `origin/main` (`36ffb78`) | ❌ No CORS — must rebase onto `be_clone` |
| `anya_fe` | deleted | Was local experiment, removed |

---

## Handoff to Frontend (given to colleague)
File: `FRONTEND_HANDOFF.md` (uncommitted, shared manually)

Critical items:
- **Port 5173 exactly** — CORS allowlist is only `localhost:5173,127.0.0.1:5173`
- **Routes are `/admin/*`**, PATCH for suspend/reactivate
- **One Bearer token, no refresh token**
- **Super Admin 401 under vaultiq_app** — do not work around in frontend
- **No Q&A endpoints exist** — demo is tenant onboarding + isolation

---

## Next Steps (Sprint 3 on BE_accurate)

1. **Migration 007** — Fix Super Admin RLS (defect #2). Needs story ID → Gate 1 approach note.
2. **CI identity split** — Run tests as `vaultiq_app` (defect #1).
3. **VQ-201** — Re-verify Gate 6 as `vaultiq_app` once 007 lands.
4. **VQ-202, 203, 301** — Continue on their branches, merge to BE_accurate sequentially.

---

## Commands to Resume

```bash
# Backend
git checkout BE_accurate
docker ps --filter name=vaultiq-db
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000

# Tests
python -m pytest tests/ -q

# Frontend (colleague)
git checkout fe_clone
git rebase be_clone
nvm4w install 24.19.0
npm run dev     # port 5173
```