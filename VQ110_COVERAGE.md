# VQ-110 Coverage Report — Every Operation Exercised

**Generated:** 2026-09-24 | **Command:** `python -m pytest tests/ -q` → `137 passed`

## Route Coverage (from FastAPI app, verified against `tests/isolation_manifest.py`)

| Operation | Manifest | Exercising Test(s) in `tests/test_isolation_suite.py` |
|-----------|----------|---------------------------------------------------------|
| POST /auth/login | ✓ | `test_login_wrong_org_no_leak` (+ full matrix in `test_auth.py`) |
| GET /health | ✓ | `test_health_no_leak` |
| POST /invite/accept | ✓ | `test_invite_accept_cross_tenant` (+ `test_tenant_lifecycle.py`) |
| POST /auth/refresh | ✓ | `test_refresh_requires_valid_token` (+ `test_auth.py`) |
| POST /auth/logout | ✓ | `test_logout_requires_valid_token` (+ `test_auth.py`) |
| POST /documents | ✓ | `test_upload_isolation` (+ `test_documents.py`) |
| GET /documents | ✓ | `test_list_documents_cross_tenant` |
| GET /documents/usage | ✓ | `test_usage_cross_tenant` |
| GET /documents/{document_id}/preview | ✓ | `test_preview_cross_tenant` |
| GET /documents/{document_id}/download | ✓ | `test_download_cross_tenant` |
| DELETE /documents/{document_id} | ✓ | `test_delete_cross_tenant` (+ `test_documents.py`) |
| POST /admin/tenants | ✓ | `test_admin_endpoints_denied_non_super_admin`, `test_admin_cross_tenant_operations` |
| GET /admin/tenants | ✓ | `test_list_tenants_super_admin_sees_all` |
| PATCH /admin/tenants/{tenant_id}/suspend | ✓ | `test_admin_cross_tenant_operations`, `test_admin_endpoints_denied_non_super_admin` |
| PATCH /admin/tenants/{tenant_id}/reactivate | ✓ | `test_admin_cross_tenant_operations`, `test_admin_endpoints_denied_non_super_admin` |
| POST /admin/tenants/{tenant_id}/invite | ✓ | `test_admin_cross_tenant_operations`, `test_admin_endpoints_denied_non_super_admin` |
| GET /admin/tenants/{tenant_id}/audit | ✓ | `test_admin_cross_tenant_operations`, `test_admin_endpoints_denied_non_super_admin` |

## Coverage Guard

`test_route_coverage_guard` auto-discovers all routes on `app` at runtime, filters to
tenant-scoped operations, and fails unless every one is present in `ISOLATION_COVERED_ROUTES`
(`tests/isolation_manifest.py`). Adding an operation without adding it to the manifest
breaks CI → blocks merge (VQ-110 acceptance criterion 4).

## Cross-Tenant Assertions Per Operation

Every cross-tenant case asserts **both**:
1. Status is the expected refusal code (404/401/403 — no existence leak)
2. Response body contains **no** other-tenant identifier or content
   (`assert_no_cross_tenant_leak`: tenant UUID, short codes, emails, filenames, content)

## Evidence

```
python -m pytest tests/ -q
137 passed, 2 warnings in 154.08s
```

3 consecutive full-suite runs: **137 passed** each (previously 85 pass / 16 asyncpg flakes).