# VaultIQ Backend

## Project State
- Current branch: main
- Current task: VQ-101 — Tenant data model and migration
- Status: COMPLETE ✅

## Gate 3 Verification (2026-09-15)
- Migration up/down tested on seeded data
- `alembic upgrade head` → `alembic downgrade base` → `alembic upgrade head` ✅
- Model test: missing tenant_id fails for non-super_admin ✅
- Full test suite: **8/8 passed** ✅
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
- [ ] VQ-103 — Tenant context on every request
- [ ] VQ-104 — Per-tenant document storage
- [ ] VQ-105 — Tenant-scoped login and session tokens

## Key Decisions
- Ignoring HeXta/ADS migration criterion (new application)
- Using pgvector for vector search (future)
- FastEmbed for embeddings (future)
- RLS at database level for tenant isolation

## Database Tables
- tenants: id, short_code, name, status, timestamps
- users: id, tenant_id (FK), email, password_hash, role, timestamps

## RLS Policy
- Enabled on users table
- Policy: tenant_id = current_setting('app.current_tenant')::uuid
