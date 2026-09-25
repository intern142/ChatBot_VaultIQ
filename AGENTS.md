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

## Completed (VQ-101)
- [x] Project structure created
- [x] SQLAlchemy models (Tenant, User)
- [x] Alembic migration with RLS policies (raw SQL)
- [x] CHECK constraint: only super_admin can have null tenant_id
- [x] Tests written (8 tests) — **ALL PASSING**
- [x] alembic upgrade head — SUCCESS
- [x] pytest tests/test_tenant.py -v — 8 PASSED

## Tech Stack
- Backend: FastAPI (Python 3.11)
- Database: PostgreSQL 16 + pgvector
- ORM: SQLAlchemy 2.0
- Migrations: Alembic
- Auth: PyJWT (for later tasks)

## Sprint 1 Progress
- [x] VQ-101 — Tenant data model **(DONE)**
- [ ] VQ-103 — Tenant context on every request
- [ ] VQ-104 — Per-tenant document storage
- [ ] VQ-105 — Tenant-scoped login and session tokens

## Key Decisions
- Ignoring HeXta/ADS migration criterion (new application)
- Using pgvector for vector search (future)
- FastEmbed for embeddings (future)
- RLS at database level for tenant isolation
- vaultiq (superuser) owns tables; vaultiq_app gets permissions (not ownership) to enforce RLS

## Database Tables
- tenants: id, short_code, name, status, timestamps
- users: id, tenant_id (FK), email, password_hash, role, timestamps

## RLS Policy
- Enabled on users table
- Policy: tenant_id = current_setting('app.current_tenant')::uuid

## Test Results (pytest tests/test_tenant.py -v)
- test_create_tenant: PASSED
- test_create_user_with_tenant: PASSED
- test_create_user_without_tenant_fails: PASSED
- test_create_user_with_fake_tenant_fails: PASSED
- test_super_admin_without_tenant: PASSED
- test_tenant_unique_short_code: PASSED
- test_user_unique_email_per_tenant: PASSED
- test_rls_blocks_cross_tenant_read: PASSED
- **Total: 8 passed, 0 failed**

## Next Steps
1. Create PR on GitHub (manual via web UI)
2. Lead review
3. Merge to main
3. Start VQ-103 (Tenant context on every request)