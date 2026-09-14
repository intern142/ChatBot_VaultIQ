# VaultIQ Backend

## Project State
- Current branch: vq-101-tenant-model
- Current task: VQ-101 — Tenant data model and migration
- Status: In progress

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
