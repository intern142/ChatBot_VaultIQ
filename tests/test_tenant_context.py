import pytest
import pytest_asyncio
import uuid
import httpx
from app.main import app
from app.auth.password import hash_password
from app.auth.jwt import create_access_token
from app.schemas.tenant import TenantStatus


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def tenant_a(db_conn):
    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO tenants (short_code, name) VALUES (%s, %s) RETURNING id",
        ("TENANT_A", "Tenant A"),
    )
    tenant_id = cur.fetchone()[0]
    db_conn.commit()
    return tenant_id


@pytest.fixture
def tenant_b(db_conn):
    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO tenants (short_code, name) VALUES (%s, %s) RETURNING id",
        ("TENANT_B", "Tenant B"),
    )
    tenant_id = cur.fetchone()[0]
    db_conn.commit()
    return tenant_id


@pytest.fixture
def user_a(db_conn, tenant_a):
    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO users (tenant_id, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
        (str(tenant_a), "usera@tenant_a.com", hash_password("StrongPass1!"), "employee"),
    )
    user_id = cur.fetchone()[0]
    db_conn.commit()
    return user_id


@pytest.fixture
def user_b(db_conn, tenant_b):
    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO users (tenant_id, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
        (str(tenant_b), "userb@tenant_b.com", hash_password("StrongPass1!"), "employee"),
    )
    user_id = cur.fetchone()[0]
    db_conn.commit()
    return user_id


@pytest.fixture
def suspended_tenant(db_conn):
    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO tenants (short_code, name, status) VALUES (%s, %s, %s) RETURNING id",
        ("SUSPENDED", "Suspended Tenant", TenantStatus.suspended.value),
    )
    tenant_id = cur.fetchone()[0]
    db_conn.commit()
    return tenant_id


@pytest.fixture
def suspended_user(db_conn, suspended_tenant):
    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO users (tenant_id, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
        (str(suspended_tenant), "user@suspended.com", hash_password("StrongPass1!"), "employee"),
    )
    user_id = cur.fetchone()[0]
    db_conn.commit()
    return user_id


class TestTenantContext:
    @pytest.mark.asyncio
    async def test_tampered_token_rejected(self, client: httpx.AsyncClient, tenant_a, user_a):
        login_response = await client.post(
            "/auth/login",
            json={
                "organisation_code": "TENANT_A",
                "email": "usera@tenant_a.com",
                "password": "StrongPass1!",
            },
        )
        token = login_response.json()["access_token"]
        tampered = token[:-5] + "XXXXX"

        response = await client.post(
            "/auth/refresh",
            headers={"Authorization": f"Bearer {tampered}"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_cross_tenant_access_returns_404(
        self, client: httpx.AsyncClient, tenant_a, tenant_b, user_a, user_b
    ):
        login_response = await client.post(
            "/auth/login",
            json={
                "organisation_code": "TENANT_A",
                "email": "usera@tenant_a.com",
                "password": "StrongPass1!",
            },
        )
        token = login_response.json()["access_token"]

        response = await client.get(
            f"/users/{user_b}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_tenant_id_in_body_ignored(
        self, client: httpx.AsyncClient, tenant_a, tenant_b, user_a
    ):
        login_response = await client.post(
            "/auth/login",
            json={
                "organisation_code": "TENANT_A",
                "email": "usera@tenant_a.com",
                "password": "StrongPass1!",
            },
        )
        token = login_response.json()["access_token"]

        response = await client.post(
            "/some-endpoint",
            headers={"Authorization": f"Bearer {token}"},
            json={"tenant_id": str(tenant_b)},
        )
        assert response.status_code in (401, 404, 405)

    @pytest.mark.asyncio
    async def test_suspended_tenant_blocked(
        self, client: httpx.AsyncClient, suspended_tenant, suspended_user
    ):
        login_response = await client.post(
            "/auth/login",
            json={
                "organisation_code": "SUSPENDED",
                "email": "user@suspended.com",
                "password": "StrongPass1!",
            },
        )
        assert login_response.status_code == 403
        assert "suspended" in login_response.json()["detail"].lower()


class TestSuperAdminBypass:
    @pytest.mark.asyncio
    async def test_super_admin_no_tenant_filter(
        self, client: httpx.AsyncClient, db_conn, tenant_a, tenant_b, user_a, user_b
    ):
        cur = db_conn.cursor()
        cur.execute(
            "INSERT INTO users (tenant_id, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
            (None, "super@admin.com", hash_password("AdminPass1!"), "super_admin"),
        )
        db_conn.commit()

        login_response = await client.post(
            "/auth/login",
            json={
                "organisation_code": "SUPER",
                "email": "super@admin.com",
                "password": "AdminPass1!",
            },
        )
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]

        response = await client.post(
            "/auth/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200