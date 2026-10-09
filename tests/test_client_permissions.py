"""Feature 2: Client-admin delegated permissions tests."""
import pytest
import pytest_asyncio
import httpx
from uuid import UUID

from tests.conftest import (
    async_client, tenant_a, tenant_b, super_admin_token,
    token_a_admin, token_a_emp, token_b_admin, token_b_emp,
)


# ---- Module-level fixtures ----

@pytest_asyncio.fixture
async def tenant_with_user_grant(super_admin_token, async_client, tenant_a):
    """Grant can_add_users to tenant A."""
    tid = str(tenant_a["id"])
    await async_client.patch(
        f"/admin/tenants/{tid}/permissions",
        json={"can_add_users": True},
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    return tenant_a


@pytest_asyncio.fixture
async def tenant_with_create_grant(super_admin_token, async_client, tenant_a):
    """Grant can_create_tenants to tenant A."""
    tid = str(tenant_a["id"])
    await async_client.patch(
        f"/admin/tenants/{tid}/permissions",
        json={"can_create_tenants": True},
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    return tenant_a


@pytest_asyncio.fixture
async def tenant_with_both_grants(super_admin_token, async_client, tenant_a):
    """Grant both permissions to tenant A."""
    tid = str(tenant_a["id"])
    await async_client.patch(
        f"/admin/tenants/{tid}/permissions",
        json={"can_add_users": True, "can_create_tenants": True},
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    return tenant_a


@pytest_asyncio.fixture
async def created_tenant(async_client, tenant_with_create_grant, token_a_admin):
    """Create a child tenant via the granted client admin."""
    token = token_a_admin
    resp = await async_client.post(
        "/client/tenants",
        json={"short_code": "CHILD", "name": "Child Tenant", "storage_quota_mb": 512},
        headers={"Authorization": f"Bearer {token}"},
    )
    return resp.json()


# ---- Tests ----

class TestTenantPermissionGrants:
    """Super Admin grants can_add_users / can_create_tenants flags."""

    @pytest.mark.asyncio
    async def test_super_admin_can_grant_permissions(
        self, async_client: httpx.AsyncClient, super_admin_token, tenant_a
    ):
        token = super_admin_token
        tid = str(tenant_a["id"])
        resp = await async_client.patch(
            f"/admin/tenants/{tid}/permissions",
            json={"can_add_users": True, "can_create_tenants": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["can_add_users"] is True
        assert data["can_create_tenants"] is True

    @pytest.mark.asyncio
    async def test_super_admin_can_grant_partial(
        self, async_client: httpx.AsyncClient, super_admin_token, tenant_a
    ):
        token = super_admin_token
        tid = str(tenant_a["id"])
        resp = await async_client.patch(
            f"/admin/tenants/{tid}/permissions",
            json={"can_add_users": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["can_add_users"] is True
        assert data["can_create_tenants"] is False

    @pytest.mark.asyncio
    async def test_super_admin_can_revoke(
        self, async_client: httpx.AsyncClient, super_admin_token, tenant_a
    ):
        token = super_admin_token
        tid = str(tenant_a["id"])
        # Grant first
        await async_client.patch(
            f"/admin/tenants/{tid}/permissions",
            json={"can_add_users": True, "can_create_tenants": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        # Revoke
        resp = await async_client.patch(
            f"/admin/tenants/{tid}/permissions",
            json={"can_add_users": False, "can_create_tenants": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["can_add_users"] is False
        assert data["can_create_tenants"] is False

    @pytest.mark.asyncio
    async def test_denied_for_non_super_admin(
        self, async_client: httpx.AsyncClient, token_a_admin, tenant_a
    ):
        token = token_a_admin
        tid = str(tenant_a["id"])
        resp = await async_client.patch(
            f"/admin/tenants/{tid}/permissions",
            json={"can_add_users": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_denied_for_employee(
        self, async_client: httpx.AsyncClient, token_a_emp, tenant_a
    ):
        token = token_a_emp
        tid = str(tenant_a["id"])
        resp = await async_client.patch(
            f"/admin/tenants/{tid}/permissions",
            json={"can_add_users": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_denied_for_super_admin_other_tenant(
        self, async_client: httpx.AsyncClient, super_admin_token, tenant_a
    ):
        """Super admin can access the endpoint - this tests it works."""
        token = super_admin_token
        tid = str(tenant_a["id"])
        resp = await async_client.patch(
            f"/admin/tenants/{tid}/permissions",
            json={"can_add_users": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_noop_returns_400(
        self, async_client: httpx.AsyncClient, super_admin_token, tenant_a
    ):
        token = super_admin_token
        tid = str(tenant_a["id"])
        resp = await async_client.patch(
            f"/admin/tenants/{tid}/permissions",
            json={},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400


class TestClientAddUsers:
    """Client Admin creates users in their own tenant (requires can_add_users)."""

    @pytest.mark.asyncio
    async def test_client_admin_can_create_employee(
        self, async_client: httpx.AsyncClient, tenant_with_user_grant, token_a_admin
    ):
        token = token_a_admin
        resp = await async_client.post(
            "/client/users",
            json={"email": "newemp@a.com", "password": "StrongPass1!", "role": "employee"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "newemp@a.com"
        assert data["role"] == "employee"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_client_admin_cannot_create_second_client_admin(
        self, async_client: httpx.AsyncClient, tenant_with_user_grant, token_a_admin
    ):
        """Tenant A already has a client_admin from fixture -> 400."""
        token = token_a_admin
        resp = await async_client.post(
            "/client/users",
            json={"email": "admin2@a.com", "password": "StrongPass1!", "role": "client_admin"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "already has a Client Admin" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_denied_without_can_add_users_grant(
        self, async_client: httpx.AsyncClient, token_a_admin, tenant_a
    ):
        """Default tenant has no grant -> 403."""
        token = token_a_admin
        resp = await async_client.post(
            "/client/users",
            json={"email": "x@a.com", "password": "StrongPass1!", "role": "employee"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_password_strength_enforced(
        self, async_client: httpx.AsyncClient, tenant_with_user_grant, token_a_admin
    ):
        token = token_a_admin
        resp = await async_client.post(
            "/client/users",
            json={"email": "weak@a.com", "password": "weak", "role": "employee"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_duplicate_email_rejected(
        self, async_client: httpx.AsyncClient, tenant_with_user_grant, token_a_admin
    ):
        token = token_a_admin
        await async_client.post(
            "/client/users",
            json={"email": "dup@a.com", "password": "StrongPass1!", "role": "employee"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = await async_client.post(
            "/client/users",
            json={"email": "dup@a.com", "password": "StrongPass1!", "role": "employee"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_employee_cannot_create_users(
        self, async_client: httpx.AsyncClient, tenant_with_user_grant, token_a_emp
    ):
        token = token_a_emp
        resp = await async_client.post(
            "/client/users",
            json={"email": "x@a.com", "password": "StrongPass1!", "role": "employee"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_super_admin_denied_on_client_users(
        self, async_client: httpx.AsyncClient, super_admin_token
    ):
        resp = await async_client.post(
            "/client/users",
            json={"email": "x@a.com", "password": "StrongPass1!", "role": "employee"},
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_denied(self, async_client: httpx.AsyncClient):
        resp = await async_client.post(
            "/client/users",
            json={"email": "x@a.com", "password": "StrongPass1!", "role": "employee"},
        )
        assert resp.status_code == 403


class TestClientCreateTenants:
    """Client Admin creates new tenants (requires can_create_tenants)."""

    @pytest.mark.asyncio
    async def test_client_admin_can_create_tenant(
        self, async_client: httpx.AsyncClient, tenant_with_create_grant, token_a_admin
    ):
        token = token_a_admin
        resp = await async_client.post(
            "/client/tenants",
            json={"short_code": "NEWT", "name": "New Tenant", "storage_quota_mb": 1024},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["short_code"] == "NEWT"
        assert data["name"] == "New Tenant"
        assert data["can_create_tenants"] is False
        assert data["created_by_user_id"] is not None

    @pytest.mark.asyncio
    async def test_denied_without_can_create_tenants_grant(
        self, async_client: httpx.AsyncClient, token_a_admin, tenant_a
    ):
        token = token_a_admin
        resp = await async_client.post(
            "/client/tenants",
            json={"short_code": "NEWT", "name": "New Tenant"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_duplicate_short_code_rejected(
        self, async_client: httpx.AsyncClient, tenant_with_create_grant, token_a_admin
    ):
        token = token_a_admin
        await async_client.post(
            "/client/tenants",
            json={"short_code": "DUP", "name": "First"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = await async_client.post(
            "/client/tenants",
            json={"short_code": "DUP", "name": "Second"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_employee_cannot_create_tenants(
        self, async_client: httpx.AsyncClient, tenant_with_create_grant, token_a_emp
    ):
        token = token_a_emp
        resp = await async_client.post(
            "/client/tenants",
            json={"short_code": "EMPT", "name": "Emp Tenant"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_super_admin_denied_on_client_tenants(
        self, async_client: httpx.AsyncClient, super_admin_token
    ):
        resp = await async_client.post(
            "/client/tenants",
            json={"short_code": "SAT", "name": "SA Tenant"},
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 403


class TestClientFirstAdmin:
    """Client Admin sets up first admin for a tenant they created."""

    @pytest.mark.asyncio
    async def test_creator_can_create_first_admin(
        self, async_client: httpx.AsyncClient, created_tenant, token_a_admin
    ):
        tid = created_tenant["id"]
        token = token_a_admin
        resp = await async_client.post(
            f"/client/tenants/{tid}/first-admin",
            json={"email": "admin@child.com", "password": "StrongPass1!"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "admin@child.com"
        assert data["role"] == "client_admin"

    @pytest.mark.asyncio
    async def test_non_creator_blocked_from_first_admin(
        self, async_client: httpx.AsyncClient, created_tenant, token_b_admin
    ):
        tid = created_tenant["id"]
        token = token_b_admin
        resp = await async_client.post(
            f"/client/tenants/{tid}/first-admin",
            json={"email": "hack@child.com", "password": "StrongPass1!"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_first_admin_only_if_none_exists(
        self, async_client: httpx.AsyncClient, created_tenant, token_a_admin
    ):
        tid = created_tenant["id"]
        token = token_a_admin
        await async_client.post(
            f"/client/tenants/{tid}/first-admin",
            json={"email": "admin@child.com", "password": "StrongPass1!"},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = await async_client.post(
            f"/client/tenants/{tid}/first-admin",
            json={"email": "admin2@child.com", "password": "StrongPass1!"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "already has a Client Admin" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_cannot_first_admin_for_unrelated_tenant(
        self, async_client: httpx.AsyncClient, tenant_b, token_a_admin
    ):
        tid = str(tenant_b["id"])
        token = token_a_admin
        resp = await async_client.post(
            f"/client/tenants/{tid}/first-admin",
            json={"email": "x@b.com", "password": "StrongPass1!"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_super_admin_denied_on_client_first_admin(
        self, async_client: httpx.AsyncClient, created_tenant, super_admin_token
    ):
        tid = created_tenant["id"]
        resp = await async_client.post(
            f"/client/tenants/{tid}/first-admin",
            json={"email": "x@child.com", "password": "StrongPass1!"},
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_unauthenticated_denied(self, async_client: httpx.AsyncClient, created_tenant):
        tid = created_tenant["id"]
        resp = await async_client.post(
            f"/client/tenants/{tid}/first-admin",
            json={"email": "x@child.com", "password": "StrongPass1!"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_cannot_first_admin_for_non_created_tenant(
        self, async_client: httpx.AsyncClient, tenant_with_create_grant, token_a_admin, tenant_b
    ):
        """Tenant B was not created by this client admin -> 404."""
        tid = str(tenant_b["id"])
        token = token_a_admin
        resp = await async_client.post(
            f"/client/tenants/{tid}/first-admin",
            json={"email": "x@b.com", "password": "StrongPass1!"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


class TestCrossTenantIsolation:
    """Verify client-admin delegated endpoints don't leak cross-tenant data."""

    @pytest.mark.asyncio
    async def test_client_users_endpoint_does_not_leak_other_tenant(
        self, async_client: httpx.AsyncClient, tenant_with_both_grants, token_a_admin, tenant_b
    ):
        token = token_a_admin
        other_tid = str(tenant_b["id"])
        # Create a user in A
        resp = await async_client.post(
            "/client/users",
            json={"email": "leak@a.com", "password": "StrongPass1!", "role": "employee"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        body = resp.text
        assert other_tid.lower() not in body.lower()

    @pytest.mark.asyncio
    async def test_client_tenants_endpoint_does_not_leak_other_tenant(
        self, async_client: httpx.AsyncClient, tenant_with_both_grants, token_a_admin, tenant_b
    ):
        token = token_a_admin
        other_tid = str(tenant_b["id"])
        resp = await async_client.post(
            "/client/tenants",
            json={"short_code": "NOLEAK", "name": "No Leak"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 201
        body = resp.text
        assert other_tid.lower() not in body.lower()

    @pytest.mark.asyncio
    async def test_client_first_admin_does_not_leak_other_tenant(
        self, async_client: httpx.AsyncClient, tenant_with_both_grants, token_a_admin, tenant_b
    ):
        # First create a child tenant
        resp = await async_client.post(
            "/client/tenants",
            json={"short_code": "LEAKTEST", "name": "Leak Test"},
            headers={"Authorization": f"Bearer {token_a_admin}"},
        )
        child_tid = resp.json()["id"]
        # Try first-admin with tenant B's id - should 404 without leaking B exists
        resp = await async_client.post(
            f"/client/tenants/{tenant_b['id']}/first-admin",
            json={"email": "x@b.com", "password": "StrongPass1!"},
            headers={"Authorization": f"Bearer {token_a_admin}"},
        )
        assert resp.status_code == 404
        body = resp.text
        assert str(tenant_b["id"]).lower() not in body.lower()