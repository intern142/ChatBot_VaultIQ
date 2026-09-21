# Current Status

## Completed (VQ-101: Tenant Data Model and Migration)

- Tenant model with UUID id, unique short_code, name, status enum (active/suspended/offboarding/purged), timestamps
- User model with UUID id, tenant_id FK (nullable for super_admin), email, password_hash, role enum (super_admin/client_admin/employee), timestamps
- Unique constraint on (tenant_id, email) for per-tenant email uniqueness
- Check constraint: super_admin must have NULL tenant_id; all other roles require tenant_id
- Alembic migration (001_initial) creating tables, enums, indexes, and RLS policy
- RLS policy on users table: `tenant_id = current_setting('app.current_tenant')::uuid`
- All 8 tests passing:
  - test_create_tenant
  - test_create_user_with_tenant
  - test_create_user_without_tenant_fails
  - test_create_user_with_fake_tenant_fails
  - test_super_admin_without_tenant
  - test_tenant_unique_short_code
  - test_user_unique_email_per_tenant
  - test_rls_blocks_cross_tenant_read
- Migration up/down/up verified successfully

## Completed (VQ-103: Tenant Context & Staff/Admin APIs)

- Added `is_active` boolean field to User model (default true) to track active employees
- Added `manager_id` self-referential FK to User model for admin → subordinates hierarchy
- Created migration 002_add_is_active_and_manager.py
- Added API endpoints under `/tenants/{tenant_id}/`:
  - `GET /staff` — List active employees (role=employee, is_active=true)
  - `GET /admins` — List admins (role=client_admin, is_active=true)
  - `GET /admins/{admin_id}/subordinates` — Get admin with their direct reports
  - `GET /users/{user_id}` — Get specific user
  - `PATCH /users/{user_id}` — Update user (role, manager, is_active)
- Updated schemas: UserCreate, UserUpdate, UserResponse, UserWithSubordinates

## Remaining (Sprint 1)

- [ ] VQ-103 (full) — Tenant context middleware on every request (set `app.current_tenant`)
- [ ] VQ-104 — Per-tenant document storage
- [ ] VQ-105 — Tenant-scoped login and session tokens

## Files Changed

- `app/models/tenant.py` — Tenant SQLAlchemy model
- `app/models/user.py` — User SQLAlchemy model (added is_active, manager_id, relationship)
- `app/models/__init__.py` — Model exports
- `alembic/versions/001_initial.py` — Initial migration with RLS
- `alembic/versions/002_add_is_active_and_manager.py` — Added is_active and manager_id columns
- `app/schemas/user.py` — User schemas (added is_active, manager_id, UserWithSubordinates)
- `app/schemas/tenant.py` — Tenant schemas (enums)
- `app/routers.py` — New: Tenant staff/admin API endpoints
- `app/main.py` — Updated to include tenants router
- `tests/test_tenant.py` — 8 test cases covering model constraints and RLS
- `tests/conftest.py` — Test fixtures

## Bugs Discovered

- None

## Decisions Made

- Using PostgreSQL native enums for tenant_status and user_role
- RLS at database level for tenant isolation (not application-level only)
- super_admin role is the only one allowed without tenant_id
- Unique constraint on (tenant_id, email) allows same email across different tenants
- Cascade delete: deleting tenant removes all associated users
- Using UUID primary keys with gen_random_uuid()
- `is_active` defaults to true for new users
- `manager_id` is nullable, SET NULL on delete (subordinates become orphaned if manager deleted)
- Only client_admin role can be queried as "admin" in the admins endpoint
- Subordinates loaded via selectinload for efficient querying

## Next Recommended Steps

1. **VQ-103 (remaining)**: Implement tenant context middleware to set `app.current_tenant` on each request
2. Add tenant context dependency for FastAPI routes (extract from JWT/header)
3. Create tenant-scoped database session dependency
4. **VQ-104**: Design document storage schema with tenant_id
5. **VQ-105**: Implement JWT-based auth with tenant claims
6. Add tests for new staff/admin endpoints