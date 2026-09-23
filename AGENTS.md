# VaultIQ Backend

## Project State
- Current branch: vq-110-isolation-suite-v1
- Current task: VQ-110 — Isolation test suite
- Status: IN PROGRESS

## Gate 3 Verification (2026-09-23)
- Migration up/down tested on seeded data
- `alembic upgrade head` → `alembic downgrade base` → `alembic upgrade head` ✅
- Model test: missing tenant_id fails for non-super_admin ✅
- Full test suite: **8/8 passed** ✅ (requires PostgreSQL running)
- RLS cross-tenant read blocked ✅
- Post-downgrade re-apply: **8/8 passed** ✅

```
tests/test_tenant.py::test_create_tenant PASSED
tests/test_tenant.py::test_create_user_with_tenant PASSED
tests/test_tenant.py::test_create_user_without_tenant_fails PASSED
tests/test_tenant.py::test_create_user_with_fake_tenant_fails PASSED
tests/test_tenant.py::test_super_admin_without_tenant PASSED
tests/test_tenant.py::test_tenant_unique_short_code PASSED
tests/test_tenant.py::test_user_unique_email_per_tenant PASSED
tests/test_tenant.py::test_rls_blocks_cross_tenant_read PASSED
======================== 8 passed, 1 warning in 2.58s ========================
```

## Tech Stack
- Backend: FastAPI (Python 3.11)
- Database: PostgreSQL 16
- ORM: SQLAlchemy 2.0
- Migrations: Alembic
- Auth: PyJWT (for later tasks)

## Sprint 1 Progress
- [x] VQ-101 — Tenant data model (COMPLETE)
- [x] VQ-102 — RLS hardening (COMPLETE)
- [x] VQ-103 — Tenant context on every request (COMPLETE)
- [x] VQ-104 — Per-tenant document storage (COMPLETE)
- [x] VQ-105 — Tenant-scoped login and session tokens (COMPLETE)
- [x] VQ-106 — Permissions matrix (COMPLETE)
- [x] VQ-107 — Tenant lifecycle (invites, audit, suspend/reactivate) (COMPLETE)

## Key Decisions
- Ignoring HeXta/ADS migration criterion (new application)
- Using pgvector for vector search (future)
- FastEmbed for embeddings (future)
- RLS at database level for tenant isolation

## Database Tables
- tenants: id, short_code, name, status, timestamps
- users: id, tenant_id (FK), email, password_hash, role, timestamps

## RLS Policy
- Enabled on users table (FORCE ROW LEVEL SECURITY)
- Policy: tenant_id = current_setting('app.current_tenant', true)::uuid
- Enabled on sessions table (FORCE ROW LEVEL SECURITY)
- Policy: tenant_id = current_setting('app.current_tenant', true)::uuid
- Enabled on documents table (FORCE ROW LEVEL SECURITY)
- Policy: tenant_id = current_setting('app.current_tenant', true)::uuid
- Enabled on invites table (FORCE ROW LEVEL SECURITY)
- Policy: tenant_id = current_setting('app.current_tenant', true)::uuid
- Enabled on audit_logs table (FORCE ROW LEVEL SECURITY)
- Policy: tenant_id = current_setting('app.current_tenant', true)::uuid

## Auth Endpoints
- POST /auth/login — Login with organisation_code, email, password → JWT token
- POST /auth/refresh — Refresh token (requires valid Bearer token)
- POST /auth/logout — Revoke session (requires valid Bearer token)
- GET /health — Health check (no auth required)

## Admin Endpoints (super_admin only)
- POST /admin/tenants — Create tenant (short_code, name, storage_quota_mb)
- GET /admin/tenants — List all tenants (no RLS filter)
- PATCH /admin/tenants/{id}/suspend — Suspend: status=suspended, revoke ALL sessions
- PATCH /admin/tenants/{id}/reactivate — Reactivate: status=active
- POST /admin/tenants/{id}/invite — Create one-time, time-limited invite for first Client Admin
- GET /admin/tenants/{id}/audit — Audit log for tenant

## Public Invite Endpoint
- POST /invite/accept — Accept invite (code, password) → creates client_admin, marks invite used

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
  database.py        — Async SQLAlchemy engine, session, Base + set_tenant_context
  main.py            — FastAPI app with routers
  auth/
    __init__.py
    password.py      — bcrypt hash/verify + strength validation
    jwt.py           — create_access_token, decode_token (PyJWT)
    dependencies.py  — get_current_user FastAPI dependency
    permissions.py   — ROLE_MATRIX, require_roles()
  models/
    __init__.py
    base.py
    tenant.py        — Tenant model
    user.py          — User model
    session.py       — Session model (token tracking, revocation, tenant_id)
    document.py      — Document model
    invite.py        — Invite model
    audit_log.py     — AuditLog model
  routes/
    __init__.py
    auth.py          — Login, refresh, logout endpoints
    documents.py     — Document CRUD, preview, download, usage
    admin.py         — Tenant lifecycle (create/suspend/reactivate/invite/audit) — super_admin only
    invite.py        — POST /invite/accept — public invite acceptance
  schemas/
    __init__.py
    auth.py          — LoginRequest, TokenResponse, RefreshRequest, MessageResponse
    tenant.py        — TenantCreate, TenantResponse, TenantStatus
    user.py          — UserCreate, UserResponse
    document.py      — DocumentResponse, DocumentListResponse, StorageUsageResponse
  services/
    storage.py       — File save/delete with tenant isolation
tests/
  __init__.py
  conftest.py        — DB fixtures (async engine, session, db_conn, app_db_engine, app_db_session)
  test_tenant.py     — 8 tests for VQ-101
  test_auth.py       — 18 tests for VQ-105
  test_tenant_context.py — 5 tests for VQ-103
  test_documents.py  — 13 tests for VQ-104
  test_rls.py        — 15 tests for VQ-102 (RLS isolation, roles, async ORM)
  test_permissions.py — 21 tests for VQ-106
  test_tenant_lifecycle.py — 21 tests for VQ-107
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
.github/
  CHECKLIST.md       — Review checklist and common mistakes
  workflows/
    test.yml         — CI pipeline (PostgreSQL, alembic, pytest)
```

## CI Pipeline
**File:** `.github/workflows/test.yml`
- Triggers: push to feature branches (`vq-105-tenant-login`, `vq-103-tenant-middleware`, `vq-104-storage-namespace`, `vq-102-rls`, `vq-106-permissions`, `vq-107-tenant-lifecycle`), PR to `main`
- Services: `pgvector/pgvector:pg16` on port 5432
- Steps: checkout → setup Python 3.11 → install deps → wait for PG → alembic upgrade head → create vaultiq_app role + grants → pytest tests/
- Status: Running (check https://github.com/intern142/ChatBot_VaultIQ/actions)

## Tooling
- `winget install GitHub.cli` — **done**
- `gh auth login` — **done** (authenticated as intern142, HTTPS protocol)
- `gh repo view intern142/ChatBot_VaultIQ` — **done** (repo access verified)
