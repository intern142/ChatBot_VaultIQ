# VaultIQ Backend

## Project State
- Current branch: vq-105-login-tokens
- Current task: VQ-105 — Tenant-scoped login and session tokens
- Status: In progress

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

## Tech Stack
- Backend: FastAPI (Python 3.11)
- Database: PostgreSQL 16 (Docker: vaultiq-db, port 5433)
- ORM: SQLAlchemy 2.0 (async)
- Migrations: Alembic
- Auth: PyJWT (VQ-105)

## Sprint 1 Progress
- [x] VQ-101 — Tenant data model (COMPLETE)
- [ ] VQ-105 — Tenant-scoped login and session tokens (IN PROGRESS — current)
- [ ] VQ-103 — Tenant context on every request (depends on VQ-105)
- [ ] VQ-104 — Per-tenant document storage (depends on VQ-103)

## Task Dependency Chain
```
VQ-101 ✅ → VQ-105 (current) → VQ-103 → VQ-104
```

## Key Decisions
- Ignoring HeXta/ADS migration criterion (new application)
- Using pgvector for vector search (future)
- FastEmbed for embeddings (future)
- RLS at database level for tenant isolation
- VQ-105 before VQ-103 (dependency chain)

## Database Tables
- tenants: id, short_code, name, status, timestamps
- users: id, tenant_id (FK), email, password_hash, role, timestamps

## RLS Policy
- Enabled on users table
- Policy: tenant_id = current_setting('app.current_tenant')::uuid

## Project Structure
```
app/
  __init__.py
  config.py          — Settings (pydantic-settings)
  database.py        — Async SQLAlchemy engine, session, Base
  main.py            — FastAPI app with /health endpoint
  models/
    __init__.py
    base.py
    tenant.py        — Tenant model
    user.py          — User model
  schemas/
    __init__.py
    tenant.py        — TenantCreate, TenantResponse
    user.py          — UserCreate, UserResponse
tests/
  __init__.py
  conftest.py        — DB fixtures (async engine, session)
  test_tenant.py     — 8 tests for VQ-101
alembic/
  env.py
  versions/
    001_initial.py   — Tenants + Users + RLS migration
.github/
  CHECKLIST.md       — Review checklist and common mistakes
```
