# VQ-110 Approach Note — Cross-tenant Isolation Test Suite v1

## Objective
Build a permanent, automated proof that tenant A cannot touch tenant B through any operation the system exposes — and that stays true as new operations are added.

## Fixture Design

### Two Fully Populated Test Tenants
Reuse and extend existing fixtures in `conftest.py`:
- **tenant_a**: client_admin (token_a_admin), employee (token_a_emp), document (doc_a), invite (invite_code_a)
- **tenant_b**: client_admin (token_b_admin), employee (token_b_emp), document (doc_b), invite (invite_code_b)
- **super_admin_token**: platform operator with no tenant

All fixtures are function-scoped with DB truncation between tests (via `db_conn` fixture).

### Additional Fixtures Needed
- `doc_a`, `doc_b` — upload via API (already exist)
- `invite_code_a`, `invite_code_b` — create via admin API (already exist)
- Potentially: session fixtures for refresh/logout tests

## Route Discovery — Single Source of Truth

**File:** `tests/isolation_manifest.py` — `ISOLATION_COVERED_ROUTES` set

This manifest is the authoritative list of every tenant-scoped operation. It categorizes routes by access pattern:
1. **Public (no auth)** — still must not leak cross-tenant info
2. **Authenticated (any role)** — token-validated endpoints
3. **Documents (tenant users only)** — super_admin explicitly denied
4. **Admin (super_admin only)** — tenant-scoped but operator-facing

**Coverage Guard:** A test (`test_route_coverage_guard`) will:
- Discover all routes from `app.main.app.routes`
- Filter to tenant-scoped routes (those with `/documents`, `/admin`, `/auth/refresh`, `/auth/logout`, `/invite/accept`)
- Assert every such route appears in `ISOLATION_COVERED_ROUTES`
- Fail if any route is missing → blocks PR merge

## Resource ID Mapping Per Route

| Route | Path Param | Tenant A Resource | Tenant B Resource | Cross-Tenant Test |
|-------|------------|-------------------|-------------------|-------------------|
| GET /documents/{id}/preview | document_id | doc_a["id"] | doc_b["id"] | A's token + B's doc_id |
| GET /documents/{id}/download | document_id | doc_a["id"] | doc_b["id"] | A's token + B's doc_id |
| DELETE /documents/{id} | document_id | doc_a["id"] | doc_b["id"] | A's token + B's doc_id |
| PATCH /admin/tenants/{id}/suspend | tenant_id | tenant_a["id"] | tenant_b["id"] | A's token (super_admin) + B's tenant_id |
| PATCH /admin/tenants/{id}/reactivate | tenant_id | tenant_a["id"] | tenant_b["id"] | A's token + B's tenant_id |
| POST /admin/tenants/{id}/invite | tenant_id | tenant_a["id"] | tenant_b["id"] | A's token + B's tenant_id |
| GET /admin/tenants/{id}/audit | tenant_id | tenant_a["id"] | tenant_b["id"] | A's token + B's tenant_id |

**Note:** Admin routes use super_admin token. The test verifies that even super_admin cannot operate on another tenant's resources via path param manipulation (though admin routes are supposed to see all tenants — the isolation is at the *data* level: suspending tenant B while authenticated as tenant A's super_admin context must not leak B's data).

## Test Matrix

For each route in `ISOLATION_COVERED_ROUTES`, exercise:

| Credential | Target Resource | Expected |
|------------|-----------------|----------|
| token_a_admin | B's resource_id | 404 (not 403 — no leak of existence) |
| token_a_emp | B's resource_id | 404 |
| token_b_admin | A's resource_id | 404 |
| token_b_emp | A's resource_id | 404 |

**Special cases:**
- **POST /auth/login**: Test wrong org_code, wrong email, wrong password all return identical 401 + "Invalid credentials" (already covered in test_auth.py — will verify in suite)
- **POST /invite/accept**: Test invite_code_b with tenant A's context (should fail — code bound to tenant B)
- **Admin routes**: Only super_admin_token has access. Test that super_admin cannot use tenant A context to operate on tenant B's admin endpoints (they can list all, but suspend/reactivate/invite/audit on B's ID should work since super_admin manages all — but must verify no data leakage in responses)
- **GET /admin/tenants**: Should return both tenants (super_admin sees all) — verify no tenant data from B leaks when A's token used (A's token is rejected 403 by permissions)

## Response Body Checks — Not Just Status Codes

For every cross-tenant request, assert:
1. **Status code** is 404 (or 401/403 for permission-denied cases)
2. **Response body** does NOT contain:
   - Any tenant B identifier (tenant_id, short_code, name)
   - Any resource content (document original_filename, preview text, invite code, email)
   - Any user emails from tenant B
   - Any audit log entries from tenant B

This prevents "soft leaks" where a 404 body accidentally includes the resource detail.

## Adding New Operations

**Rule:** Adding a new tenant-scoped route without adding it to `ISOLATION_COVERED_ROUTES` causes `test_route_coverage_guard` to fail → CI blocks merge.

Process:
1. Add route to `ISOLATION_COVERED_ROUTES` in `isolation_manifest.py`
2. Add cross-tenant test case in `test_isolation_suite.py`
3. Run suite → green
4. PR passes

## What Could Go Wrong

| Risk | Mitigation |
|------|------------|
| Missing a route in manifest | Coverage guard test auto-discovers routes from FastAPI app |
| Response body leaks data | Explicit body assertions in every test case |
| New route added without test | Coverage guard fails CI |
| Super admin admin-endpoint leakage | Test admin routes with super_admin token against both tenant IDs, verify response data isolation |
| Invite code cross-tenant accept | Test invite_code_b with token_a (should 400, not leak B's tenant) |
| Flaky tests on Windows | Use existing async_client fixture; individual test runs pass |

## Test File Structure

**New file:** `tests/test_isolation_suite.py`

- `test_route_coverage_guard()` — ensures manifest completeness
- Parametrized test `test_cross_tenant_isolation` — iterates over manifest routes, credentials, target resources
- Helper to build request (method, path with resolved IDs, headers, body)
- Body assertion helper — checks for forbidden substrings

## Gates

1. **Gate 1** — This approach note (reviewer approves)
2. **Gate 2** — Implement on branch `vq-110-isolation-suite-v1`
3. **Gate 3** — Tests written, full suite green, coverage report attached
4. **Gate 4** — Self-review: confirm body checks, tick checklist, open PR
5. **Gate 5** — Code review
6. **Gate 6** — Run suite against live container (Docker), paste output
7. **Gate 7** — Demo Friday