# VaultIQ Backend

## Project State
- Current branch: vq-101-tenant-model
- Current task: VQ-101 — Tenant data model and migration
- Status: In progress — BLOCKED (Python not installed)

## Blockers
- Python 3.11 not installed on system
- Admin password required to install Python
- Admin person unavailable — will install when available
- PostgreSQL container is running (vaultiq-db)

## Completed (VQ-101)
- Project structure created
- SQLAlchemy models (Tenant, User)
- Alembic migration with RLS policies
- Tests written (8 tests)
- Committed and pushed to branch vq-101-tenant-model

## Remaining (VQ-101)
- Install Python 3.11 (need admin)
- pip install dependencies
- Run alembic upgrade head
- Run pytest
- Verify on live container
- Merge to main after approval

## Tech Stack
- Backend: FastAPI (Python 3.11)
- Database: PostgreSQL 16
- ORM: SQLAlchemy 2.0
- Migrations: Alembic
- Auth: PyJWT (for later tasks)

## Sprint 1 Progress
- [ ] VQ-101 — Tenant data model (IN PROGRESS)
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
