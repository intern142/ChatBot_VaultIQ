# APPROACH - VQ-302: Client Admin Dashboard Data

## Objective
Provide tenant-scoped dashboard data for Client Admins only.

## Endpoints (Client Admin only, super_admin denied)
- GET /dashboard/overview
- GET /dashboard/overview/30d
- GET /dashboard/documents
- GET /dashboard/users
- GET /dashboard/audit
- GET /dashboard/feedback
- GET /dashboard/knowledge-gaps
- GET /dashboard/export/{entity} as CSV

## Implementation
1. Schemas in app/schemas/dashboard.py
2. Routes in app/routes/dashboard.py with require_roles_with_tenant("client_admin")
3. Queries strictly filtered by tenant_id from token context
4. CSV exports: formula-safe (prefix dangerous chars with apostrophe), audited in audit_logs
5. Add dashboard routes to tests/isolation_manifest.py
6. Tests in tests/test_dashboard.py
7. Respect existing RLS; never trust client params for tenant
