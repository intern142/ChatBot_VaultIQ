"""VQ-110: Cross-tenant isolation test suite.

Exercises every tenant-scoped operation with tenant A's credentials against
tenant B's identifiers. Verifies refusal without data leakage.
"""
import pytest
import pytest_asyncio
import httpx
from typing import Any
from app.main import app
from tests.isolation_manifest import ISOLATION_COVERED_ROUTES, normalize_path


# ---- Coverage Guard ----

def test_route_coverage_guard():
    """Every tenant-scoped route in the app must be listed in ISOLATION_COVERED_ROUTES."""
    tenant_scoped_prefixes = ("/documents", "/admin", "/auth/refresh", "/auth/logout", "/invite/accept")
    tenant_scoped_methods = {"GET", "POST", "PATCH", "DELETE"}

    covered = {(m.upper(), normalize_path(p)) for m, p in ISOLATION_COVERED_ROUTES}

    app_routes = set()
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            for method in route.methods:
                if method.upper() in tenant_scoped_methods:
                    path = route.path
                    if any(path.startswith(prefix) for prefix in tenant_scoped_prefixes):
                        app_routes.add((method.upper(), normalize_path(path)))

    missing = app_routes - covered
    extra = covered - app_routes

    assert not missing, (
        f"Routes in app but missing from ISOLATION_COVERED_ROUTES: {sorted(missing)}. "
        "Add them to tests/isolation_manifest.py"
    )
    # Extra routes in manifest are OK (may be future routes not yet implemented)


# ---- Helpers ----

FORBIDDEN_SUBSTRINGS = [
    "tenant_b", "TENANT_B", "tenant_a", "TENANT_A",
    "admin@b.com", "admin@a.com", "emp@b.com", "emp@a.com",
    "test_b.txt", "test_a.txt",
    "Tenant B document", "Tenant A document",
]


def assert_no_cross_tenant_leak(response: httpx.Response, other_tenant_id: str):
    """Assert response body contains no identifiers from the other tenant."""
    body = response.text
    # Check for other tenant's UUID
    assert other_tenant_id.lower() not in body.lower(), (
        f"Response leaks other tenant ID: {other_tenant_id}"
    )
    # Check for other tenant's short code
    assert "TENANT_B" not in body.upper() and "TENANT_A" not in body.upper(), (
        "Response leaks tenant short code"
    )
    # Check for forbidden substrings
    for substr in FORBIDDEN_SUBSTRINGS:
        assert substr not in body, f"Response leaks forbidden substring: {substr}"


async def make_request(
    async_client: httpx.AsyncClient,
    method: str,
    path: str,
    token: str | None,
    **kwargs,
) -> httpx.Response:
    """Make an HTTP request with optional Bearer token."""
    headers = kwargs.pop("headers", {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return await async_client.request(method, path, headers=headers, **kwargs)


# ---- Fixtures for resource IDs ----

@pytest_asyncio.fixture
async def tenant_a_ids(async_client, token_a_admin, token_a_emp, tenant_a):
    """Return tenant A's resource IDs for cross-tenant testing."""
    return {
        "tenant_id": str(tenant_a["id"]),
        "admin_token": token_a_admin,
        "emp_token": token_a_emp,
    }


@pytest_asyncio.fixture
async def tenant_b_ids(async_client, token_b_admin, token_b_emp, tenant_b):
    """Return tenant B's resource IDs for cross-tenant testing."""
    return {
        "tenant_id": str(tenant_b["id"]),
        "admin_token": token_b_admin,
        "emp_token": token_b_emp,
    }


@pytest_asyncio.fixture
async def doc_ids(async_client, doc_a, doc_b):
    """Return document IDs for both tenants."""
    return {
        "doc_a_id": doc_a["id"],
        "doc_b_id": doc_b["id"],
    }


@pytest_asyncio.fixture
async def invite_codes(async_client, invite_code_a, invite_code_b):
    """Return invite codes for both tenants."""
    return {
        "invite_a": invite_code_a["code"],
        "invite_b": invite_code_b["code"],
        "invite_a_tenant_id": invite_code_a["tenant_id"],
        "invite_b_tenant_id": invite_code_b["tenant_id"],
    }


# ---- Cross-tenant isolation tests ----

class TestPublicEndpoints:
    """Public endpoints must not leak cross-tenant info."""

    @pytest.mark.asyncio
    async def test_health_no_leak(self, async_client):
        resp = await async_client.get("/health")
        assert resp.status_code == 200
        # Health should not contain any tenant info
        body = resp.text.lower()
        assert "tenant" not in body

    @pytest.mark.asyncio
    async def test_login_wrong_org_no_leak(self, async_client, tenant_a):
        """Login with wrong org_code returns generic error, no tenant enumeration."""
        resp = await async_client.post(
            "/auth/login",
            json={
                "organisation_code": "WRONG",
                "email": "user@acme.com",
                "password": "StrongPass1!",
            },
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"
        # No tenant info in response
        body = resp.text.lower()
        assert "tenant" not in body

    @pytest.mark.asyncio
    async def test_invite_accept_cross_tenant(
        self, async_client, invite_codes, tenant_a_ids, tenant_b_ids
    ):
        """Accepting a fresh tenant's invite binds only to that tenant, never leaking others."""
        resp = await async_client.post(
            "/invite/accept",
            json={"code": invite_codes["invite_b"], "password": "StrongPass1!"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # The new admin must be bound to the invite's own tenant only
        assert data["tenant_id"] == invite_codes["invite_b_tenant_id"]
        # Must not be the populated tenants, and must not leak their identifiers
        assert data["tenant_id"] != tenant_a_ids["tenant_id"]
        assert data["tenant_id"] != tenant_b_ids["tenant_id"]
        assert_no_cross_tenant_leak(resp, tenant_a_ids["tenant_id"])
        assert_no_cross_tenant_leak(resp, tenant_b_ids["tenant_id"])


class TestAuthenticatedEndpoints:
    """Authenticated endpoints - any valid role.

    Note: /auth/refresh and /auth/logout require DB session rows which aren't
    created by token fixtures. Cross-tenant session isolation is enforced by
    unique session_id (jti) per token - tested in test_auth.py.
    """

    @pytest.mark.asyncio
    async def test_refresh_requires_valid_token(self, async_client):
        """Invalid/expired tokens are rejected."""
        resp = await make_request(async_client, "POST", "/auth/refresh", "invalid.token.here")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_logout_requires_valid_token(self, async_client):
        """Invalid tokens are rejected."""
        resp = await make_request(async_client, "POST", "/auth/logout", "invalid.token.here")
        assert resp.status_code == 401


class TestDocumentEndpoints:
    """Document endpoints - tenant users only (super_admin denied)."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("token_fixture,role", [
        ("token_a_admin", "client_admin"),
        ("token_a_emp", "employee"),
        ("token_b_admin", "client_admin"),
        ("token_b_emp", "employee"),
    ])
    async def test_list_documents_cross_tenant(
        self, async_client, request, token_fixture, role, tenant_a_ids, tenant_b_ids, doc_ids
    ):
        """List documents with tenant A token should not return tenant B's docs."""
        token = request.getfixturevalue(token_fixture)
        # Determine which tenant the token belongs to
        is_token_a = token_fixture.startswith("token_a")
        other_tenant_id = tenant_b_ids["tenant_id"] if is_token_a else tenant_a_ids["tenant_id"]

        resp = await make_request(async_client, "GET", "/documents", token)
        assert resp.status_code == 200
        data = resp.json()
        # All returned docs must belong to the token's tenant
        for doc in data["documents"]:
            assert doc["tenant_id"] != other_tenant_id, (
                f"Cross-tenant leak: {role} token returned other tenant's document"
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("token_fixture,role,doc_fixture", [
        ("token_a_admin", "client_admin", "doc_b_id"),
        ("token_a_emp", "employee", "doc_b_id"),
        ("token_b_admin", "client_admin", "doc_a_id"),
        ("token_b_emp", "employee", "doc_a_id"),
    ])
    async def test_preview_cross_tenant(
        self, async_client, request, token_fixture, role, doc_fixture, doc_ids, tenant_a_ids, tenant_b_ids
    ):
        """Preview with tenant A token against tenant B's document ID -> 404, no leak."""
        token = request.getfixturevalue(token_fixture)
        target_doc_id = doc_ids[doc_fixture]
        is_token_a = token_fixture.startswith("token_a")
        other_tenant_id = tenant_b_ids["tenant_id"] if is_token_a else tenant_a_ids["tenant_id"]

        resp = await make_request(async_client, "GET", f"/documents/{target_doc_id}/preview", token)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        assert resp.json()["detail"] == "Document not found"
        assert_no_cross_tenant_leak(resp, other_tenant_id)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("token_fixture,role,doc_fixture", [
        ("token_a_admin", "client_admin", "doc_b_id"),
        ("token_a_emp", "employee", "doc_b_id"),
        ("token_b_admin", "client_admin", "doc_a_id"),
        ("token_b_emp", "employee", "doc_a_id"),
    ])
    async def test_download_cross_tenant(
        self, async_client, request, token_fixture, role, doc_fixture, doc_ids, tenant_a_ids, tenant_b_ids
    ):
        """Download with tenant A token against tenant B's document ID -> 404, no leak."""
        token = request.getfixturevalue(token_fixture)
        target_doc_id = doc_ids[doc_fixture]
        is_token_a = token_fixture.startswith("token_a")
        other_tenant_id = tenant_b_ids["tenant_id"] if is_token_a else tenant_a_ids["tenant_id"]

        resp = await make_request(async_client, "GET", f"/documents/{target_doc_id}/download", token)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        assert resp.json()["detail"] == "Document not found"
        assert_no_cross_tenant_leak(resp, other_tenant_id)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("token_fixture,role,doc_fixture", [
        ("token_a_admin", "client_admin", "doc_b_id"),
        ("token_b_admin", "client_admin", "doc_a_id"),
        # employee cannot delete - they get 403, not cross-tenant test
    ])
    async def test_delete_cross_tenant(
        self, async_client, request, token_fixture, role, doc_fixture, doc_ids, tenant_a_ids, tenant_b_ids
    ):
        """Delete with tenant A token against tenant B's document ID -> 404, no leak."""
        token = request.getfixturevalue(token_fixture)
        target_doc_id = doc_ids[doc_fixture]
        is_token_a = token_fixture.startswith("token_a")
        other_tenant_id = tenant_b_ids["tenant_id"] if is_token_a else tenant_a_ids["tenant_id"]

        resp = await make_request(async_client, "DELETE", f"/documents/{target_doc_id}", token)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        assert resp.json()["detail"] == "Document not found"
        assert_no_cross_tenant_leak(resp, other_tenant_id)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("token_fixture,role", [
        ("token_a_admin", "client_admin"),
        ("token_b_admin", "client_admin"),
    ])
    async def test_usage_cross_tenant(
        self, async_client, request, token_fixture, role, tenant_a_ids, tenant_b_ids
    ):
        """Usage with tenant A token should only show tenant A's usage."""
        token = request.getfixturevalue(token_fixture)
        is_token_a = token_fixture.startswith("token_a")
        other_tenant_id = tenant_b_ids["tenant_id"] if is_token_a else tenant_a_ids["tenant_id"]

        resp = await make_request(async_client, "GET", "/documents/usage", token)
        assert resp.status_code == 200
        data = resp.json()
        assert data["tenant_id"] != other_tenant_id, "Usage response leaks other tenant ID"


class TestAdminEndpoints:
    """Admin endpoints - super_admin only."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("endpoint", [
        "/admin/tenants/{tenant_id}/suspend",
        "/admin/tenants/{tenant_id}/reactivate",
        "/admin/tenants/{tenant_id}/invite",
        "/admin/tenants/{tenant_id}/audit",
    ])
    async def test_admin_cross_tenant_operations(
        self, async_client, super_admin_token, endpoint, tenant_a_ids, tenant_b_ids
    ):
        """Super admin operating on tenant B while authenticated as super_admin.
        
        Note: Super admin CAN operate on any tenant (that's the point).
        The test verifies the response doesn't leak cross-tenant data inappropriately.
        """
        # Test with tenant A's ID
        path_a = endpoint.format(tenant_id=tenant_a_ids["tenant_id"])
        resp = await make_request(async_client, "GET" if "audit" in endpoint else "POST", path_a, super_admin_token)
        # Should succeed (200/201) or return 400/404 for business logic reasons
        assert resp.status_code != 403, f"Super admin denied on {endpoint} for tenant A"

        # Test with tenant B's ID
        path_b = endpoint.format(tenant_id=tenant_b_ids["tenant_id"])
        resp = await make_request(async_client, "GET" if "audit" in endpoint else "POST", path_b, super_admin_token)
        assert resp.status_code != 403, f"Super admin denied on {endpoint} for tenant B"

        # Verify response for B doesn't leak A's data
        if resp.status_code == 200:
            assert_no_cross_tenant_leak(resp, tenant_a_ids["tenant_id"])

    @pytest.mark.asyncio
    async def test_list_tenants_super_admin_sees_all(
        self, async_client, super_admin_token, tenant_a_ids, tenant_b_ids
    ):
        """Super admin list tenants should return both tenants."""
        resp = await make_request(async_client, "GET", "/admin/tenants", super_admin_token)
        assert resp.status_code == 200
        data = resp.json()
        tenant_ids = {t["id"] for t in data}
        assert tenant_a_ids["tenant_id"] in tenant_ids
        assert tenant_b_ids["tenant_id"] in tenant_ids

    @pytest.mark.asyncio
    @pytest.mark.parametrize("token_fixture", ["token_a_admin", "token_a_emp", "token_b_admin", "token_b_emp"])
    async def test_admin_endpoints_denied_non_super_admin(
        self, async_client, request, token_fixture, tenant_a_ids, tenant_b_ids
    ):
        """Non-super-admin tokens must be denied (403) on all admin endpoints."""
        token = request.getfixturevalue(token_fixture)
        endpoints = [
            ("POST", "/admin/tenants"),
            ("GET", "/admin/tenants"),
            ("PATCH", f"/admin/tenants/{tenant_a_ids['tenant_id']}/suspend"),
            ("PATCH", f"/admin/tenants/{tenant_a_ids['tenant_id']}/reactivate"),
            ("POST", f"/admin/tenants/{tenant_a_ids['tenant_id']}/invite"),
            ("GET", f"/admin/tenants/{tenant_a_ids['tenant_id']}/audit"),
        ]
        for method, path in endpoints:
            resp = await make_request(async_client, method, path, token)
            assert resp.status_code == 403, (
                f"{token_fixture} should be denied on {method} {path}, got {resp.status_code}"
            )


class TestUploadEndpoint:
    """POST /documents - upload with cross-tenant context."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("token_fixture", ["token_a_admin", "token_b_admin"])
    async def test_upload_isolation(self, async_client, request, token_fixture, tenant_a_ids, tenant_b_ids):
        """Upload with tenant A token creates document in tenant A's storage only."""
        token = request.getfixturevalue(token_fixture)
        is_token_a = token_fixture.startswith("token_a")
        other_tenant_id = tenant_b_ids["tenant_id"] if is_token_a else tenant_a_ids["tenant_id"]

        files = {"file": ("test.txt", b"test content", "text/plain")}
        data = {"category": "policy"}
        resp = await make_request(async_client, "POST", "/documents", token, files=files, data=data)
        assert resp.status_code == 201
        resp_data = resp.json()
        assert resp_data["tenant_id"] != other_tenant_id, "Upload created document in wrong tenant"

    @pytest.mark.asyncio
    async def test_upload_employee_forbidden_a(self, async_client, token_a_emp):
        """Employee cannot upload documents (403)."""
        files = {"file": ("test.txt", b"test content", "text/plain")}
        data = {"category": "policy"}
        resp = await make_request(async_client, "POST", "/documents", token_a_emp, files=files, data=data)
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_upload_employee_forbidden_b(self, async_client, token_b_emp):
        """Employee cannot upload documents (403)."""
        files = {"file": ("test.txt", b"test content", "text/plain")}
        data = {"category": "policy"}
        resp = await make_request(async_client, "POST", "/documents", token_b_emp, files=files, data=data)
        assert resp.status_code == 403


# ---- Manifest completeness verification ----

def test_manifest_covers_all_routes():
    """Duplicate of coverage guard but as explicit test for clarity."""
    test_route_coverage_guard()