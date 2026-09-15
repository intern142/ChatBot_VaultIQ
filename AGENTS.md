# VaultIQ Backend

## Project State
- Current branch: vq-105-tenant-login
- Current task: VQ-105 — Tenant-scoped login and session tokens
- Status: In progress (tests passing, ready for gates)

## Blockers
- None

## Completed
### VQ-101 — Tenant data model and migration ✅
- Project structure created
- SQLAlchemy models (Tenant, User)
- Alembic migration with RLS policies
- Tests written (8 tests)
- Committed and pushed to branch vq-101-tenant-model
- Gate 3: Migration up/down verified, 8/8 tests pass
- Gate 4: Review checklist ticked, PR opened
- Gate 6: Live container verified, 8/8 tests pass
- Gate 5: Pending (reviewer approval)
- Gate 7: Pending (demo in sprint review)

### VQ-105 — Tenant-scoped login and session tokens (tests passing)
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

## Tech Stack
- Backend: FastAPI (Python 3.11)
- Database: PostgreSQL 16 (Docker: vaultiq-db, port 5433)
- ORM: SQLAlchemy 2.0 (async)
- Migrations: Alembic
- Auth: PyJWT (VQ-105)

## Sprint 1 Progress
- [x] VQ-101 — Tenant data model (COMPLETE)
- [x] VQ-105 — Tenant-scoped login and session tokens (TESTS PASSING — ready for gates)
- [ ] VQ-103 — Tenant context on every request (depends on VQ-105)
- [ ] VQ-104 — Per-tenant document storage (depends on VQ-103)

## Task Dependency Chain
```
VQ-101 ✅ → VQ-105 ✅ → VQ-103 (next) → VQ-104
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
```
