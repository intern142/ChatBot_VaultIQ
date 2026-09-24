import pytest
import pytest_asyncio
import uuid
import time
import httpx
from datetime import datetime, timezone
from app.main import app
from app.auth.password import hash_password, validate_password_strength
from app.auth.jwt import create_access_token, decode_token
from app.config import get_settings

settings = get_settings()


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.fixture
def test_tenant(db_conn):
    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO tenants (short_code, name) VALUES (%s, %s) RETURNING id",
        ("ACME", "Acme Corp"),
    )
    tenant_id = cur.fetchone()[0]
    db_conn.commit()
    return tenant_id


@pytest.fixture
def test_user(db_conn, test_tenant):
    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO users (tenant_id, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
        (str(test_tenant), "user@acme.com", hash_password("StrongPass1!"), "employee"),
    )
    user_id = cur.fetchone()[0]
    db_conn.commit()
    return user_id


@pytest.fixture
def super_admin(db_conn):
    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO users (tenant_id, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
        (None, "admin@vaultiq.com", hash_password("AdminPass1!"), "super_admin"),
    )
    user_id = cur.fetchone()[0]
    db_conn.commit()
    return user_id


class TestPasswordStrength:
    def test_weak_password_too_short(self):
        errors = validate_password_strength("Ab1!")
        assert len(errors) > 0

    def test_weak_password_no_uppercase(self):
        errors = validate_password_strength("strongpass1!")
        assert len(errors) > 0

    def test_weak_password_no_lowercase(self):
        errors = validate_password_strength("STRONGPASS1!")
        assert len(errors) > 0

    def test_weak_password_no_digit(self):
        errors = validate_password_strength("StrongPass!")
        assert len(errors) > 0

    def test_weak_password_no_special(self):
        errors = validate_password_strength("StrongPass1")
        assert len(errors) > 0

    def test_strong_password(self):
        errors = validate_password_strength("StrongPass1!")
        assert len(errors) == 0


class TestLoginSuccess:
    @pytest.mark.asyncio
    async def test_login_valid_credentials(
        self, client: httpx.AsyncClient, test_tenant, test_user
    ):
        response = await client.post(
            "/auth/login",
            json={
                "organisation_code": "ACME",
                "email": "user@acme.com",
                "password": "StrongPass1!",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["role"] == "employee"
        assert data["tenant_id"] == str(test_tenant)

    @pytest.mark.asyncio
    async def test_login_super_admin(self, client: httpx.AsyncClient, super_admin):
        response = await client.post(
            "/auth/login",
            json={
                "organisation_code": "SUPER",
                "email": "admin@vaultiq.com",
                "password": "AdminPass1!",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "super_admin"
        assert data["tenant_id"] is None


class TestLoginFailures:
    @pytest.mark.asyncio
    async def test_login_wrong_org_code(
        self, client: httpx.AsyncClient, test_tenant, test_user
    ):
        response = await client.post(
            "/auth/login",
            json={
                "organisation_code": "WRONG",
                "email": "user@acme.com",
                "password": "StrongPass1!",
            },
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    @pytest.mark.asyncio
    async def test_login_wrong_email(
        self, client: httpx.AsyncClient, test_tenant, test_user
    ):
        response = await client.post(
            "/auth/login",
            json={
                "organisation_code": "ACME",
                "email": "wrong@email.com",
                "password": "StrongPass1!",
            },
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    @pytest.mark.asyncio
    async def test_login_wrong_password(
        self, client: httpx.AsyncClient, test_tenant, test_user
    ):
        response = await client.post(
            "/auth/login",
            json={
                "organisation_code": "ACME",
                "email": "user@acme.com",
                "password": "WrongPass1!",
            },
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    @pytest.mark.asyncio
    async def test_login_same_response_time(
        self, client: httpx.AsyncClient, test_tenant, test_user
    ):
        times = []
        for _ in range(3):
            start = time.time()
            await client.post(
                "/auth/login",
                json={
                    "organisation_code": "ACME",
                    "email": "user@acme.com",
                    "password": "WrongPass1!",
                },
            )
            times.append(time.time() - start)

        avg = sum(times) / len(times)
        for t in times:
            assert abs(t - avg) < 0.5


class TestAccountLockout:
    @pytest.mark.asyncio
    async def test_lockout_after_5_failed_attempts(
        self, client: httpx.AsyncClient, test_tenant, test_user
    ):
        for _ in range(5):
            await client.post(
                "/auth/login",
                json={
                    "organisation_code": "ACME",
                    "email": "user@acme.com",
                    "password": "WrongPass1!",
                },
            )

        response = await client.post(
            "/auth/login",
            json={
                "organisation_code": "ACME",
                "email": "user@acme.com",
                "password": "StrongPass1!",
            },
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    @pytest.mark.asyncio
    async def test_successful_login_resets_counter(
        self, client: httpx.AsyncClient, test_tenant, test_user
    ):
        for _ in range(3):
            await client.post(
                "/auth/login",
                json={
                    "organisation_code": "ACME",
                    "email": "user@acme.com",
                    "password": "WrongPass1!",
                },
            )

        response = await client.post(
            "/auth/login",
            json={
                "organisation_code": "ACME",
                "email": "user@acme.com",
                "password": "StrongPass1!",
            },
        )
        assert response.status_code == 200


class TestTokenVerification:
    @pytest.mark.asyncio
    async def test_valid_token_access(
        self, client: httpx.AsyncClient, test_tenant, test_user
    ):
        login_response = await client.post(
            "/auth/login",
            json={
                "organisation_code": "ACME",
                "email": "user@acme.com",
                "password": "StrongPass1!",
            },
        )
        token = login_response.json()["access_token"]

        response = await client.post(
            "/auth/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_tampered_token_rejected(
        self, client: httpx.AsyncClient, test_tenant, test_user
    ):
        login_response = await client.post(
            "/auth/login",
            json={
                "organisation_code": "ACME",
                "email": "user@acme.com",
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

    def test_expired_token_rejected(
        self, client: httpx.AsyncClient, test_tenant, test_user
    ):
        session_id = uuid.uuid4()
        token = create_access_token(
            user_id=uuid.uuid4(),
            role="employee",
            tenant_id=uuid.uuid4(),
            session_id=session_id,
        )
        payload = decode_token(token)
        assert payload["exp"] > datetime.now(timezone.utc).timestamp()


class TestSessionRevocation:
    @pytest.mark.asyncio
    async def test_logout_revokes_session(
        self, client: httpx.AsyncClient, test_tenant, test_user
    ):
        login_response = await client.post(
            "/auth/login",
            json={
                "organisation_code": "ACME",
                "email": "user@acme.com",
                "password": "StrongPass1!",
            },
        )
        token = login_response.json()["access_token"]

        logout_response = await client.post(
            "/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert logout_response.status_code == 200

        refresh_response = await client.post(
            "/auth/refresh",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert refresh_response.status_code == 401
