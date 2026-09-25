"""VQ-107: Tenant lifecycle tests — create, suspend, reactivate, invite first admin.

Covers:
- Tenant creation (code format, uniqueness, audit trail)
- Invite create + accept, one-time use, expiry
- Suspend revokes active sessions and blocks logins within one request
- Reactivate reverses suspension
- Permission enforcement on /admin endpoints
- RLS: invites are only readable via tenant context or exact invite code
"""

import uuid
import psycopg2
import pytest
import pytest_asyncio
import httpx
from sqlalchemy import text

from app.main import app
from app.auth.jwt import create_access_token
from app.config import get_settings
from app.auth.password import hash_password

settings = get_settings()

VALID_PASSWORD = "Adm1n!Passw0rd"


# ---------------------------------------------------------------------------
# Fixtures (pattern from vq-104 tests to avoid asyncpg event-loop issues)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def db_conn():
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute("TRUNCATE users, tenants, sessions CASCADE")
    conn.commit()
    yield conn
    conn.close()


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def seed_user(db_conn, email, role, tenant_id=None):
    """Insert a user row; returns the user id as a string."""
    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO users (tenant_id, email, password_hash, role) "
        "VALUES (%s, %s, %s, %s) RETURNING id",
        (tenant_id, email, hash_password("Str0ng!Passw0rd"), role),
    )
    user_id = str(cur.fetchone()[0])
    db_conn.commit()
    return user_id


def make_token(db_conn, user_id: str, role: str, tenant_id=None) -> str:
    """Create a valid session in DB and mint a JWT for it."""
    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO sessions (user_id, tenant_id, token_hash, expires_at) "
        "VALUES (%s, %s, %s, now() + interval '1 hour') RETURNING id",
        (user_id, tenant_id, "token_hash"),
    )
    session_id = str(cur.fetchone()[0])
    db_conn.commit()
    return create_access_token(
        user_id=uuid.UUID(user_id),
        role=role,
        tenant_id=uuid.UUID(tenant_id) if tenant_id else None,
        session_id=uuid.UUID(session_id),
    )


@pytest.fixture
def super_admin_token(db_conn):
    user_id = seed_user(db_conn, "superadmin@vaultiq.com", "super_admin")
    return make_token(db_conn, user_id, "super_admin")


# ---------------------------------------------------------------------------
# Tenant creation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_tenant_and_audit_log(client, super_admin_token):
    res = await client.post(
        "/admin/tenants",
        json={"short_code": "acme", "name": "Acme Corp", "storage_quota_mb": 1000},
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["short_code"] == "ACME"
    assert body["status"] == "active"
    assert body["storage_quota_mb"] == 1000

    res = await client.get(
        f"/admin/tenants/{body['id']}/audit",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert res.status_code == 200
    logs = res.json()
    assert any(log["action"] == "create_tenant" for log in logs)
    assert logs[0]["actor_role"] == "super_admin"


@pytest.mark.asyncio
async def test_create_tenant_duplicate_code_conflict(client, super_admin_token):
    payload = {"short_code": "ACME", "name": "Acme Corp", "storage_quota_mb": 2048}
    res1 = await client.post("/admin/tenants", json=payload, headers={"Authorization": f"Bearer {super_admin_token}"})
    assert res1.status_code == 201
    res2 = await client.post("/admin/tenants", json=payload, headers={"Authorization": f"Bearer {super_admin_token}"})
    assert res2.status_code == 409


@pytest.mark.asyncio
async def test_create_tenant_rejects_bad_short_code(client, super_admin_token):
    for bad in ["a", "has space", "with.dot", "x" * 21, "low§"]:
        res = await client.post(
            "/admin/tenants",
            json={"short_code": bad, "name": "X"},
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert res.status_code == 422, f"short_code={bad!r} should be rejected"


@pytest.mark.asyncio
async def test_list_tenants_shows_all(client, super_admin_token):
    for code in ("ALFA", "BETA"):
        res = await client.post(
            "/admin/tenants",
            json={"short_code": code, "name": code, "storage_quota_mb": 2048},
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert res.status_code == 201
    res = await client.get("/admin/tenants", headers={"Authorization": f"Bearer {super_admin_token}"})
    assert res.status_code == 200
    codes = {t["short_code"] for t in res.json()}
    assert {"ALFA", "BETA"} <= codes


# ---------------------------------------------------------------------------
# Invite create + accept
# ---------------------------------------------------------------------------

async def _create_tenant_and_invite(client, token, code="NEXUS", email="admin@nexus.io"):
    res = await client.post(
        "/admin/tenants",
        json={"short_code": code, "name": "Nexus Ltd", "storage_quota_mb": 2048},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    tenant_id = res.json()["id"]

    res = await client.post(
        f"/admin/tenants/{tenant_id}/invite",
        json={"email": email, "expires_in_hours": 24},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    invite = res.json()
    assert invite["email"] == email
    assert invite["used_at"] is None
    assert len(invite["code"]) >= 20
    return tenant_id, invite["code"]


@pytest.mark.asyncio
async def test_invite_accept_creates_client_admin(client, super_admin_token, db_conn):
    tenant_id, code = await _create_tenant_and_invite(client, super_admin_token)

    res = await client.post("/invite/accept", json={"code": code, "password": VALID_PASSWORD})
    assert res.status_code == 200
    assert res.json()["tenant_id"] == tenant_id

    res = await client.post(
        "/auth/login",
        json={"organisation_code": "NEXUS", "email": "admin@nexus.io", "password": VALID_PASSWORD},
    )
    assert res.status_code == 200
    assert res.json()["role"] == "client_admin"
    assert res.json()["tenant_id"] == tenant_id

    # A second accept must fail (one-time use)
    res = await client.post("/invite/accept", json={"code": code, "password": VALID_PASSWORD})
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_invite_cannot_be_reused(client, super_admin_token):
    _, code = await _create_tenant_and_invite(client, super_admin_token)

    res1 = await client.post("/invite/accept", json={"code": code, "password": VALID_PASSWORD})
    assert res1.status_code == 200

    res2 = await client.post("/invite/accept", json={"code": code, "password": VALID_PASSWORD})
    assert res2.status_code == 400


@pytest.mark.asyncio
async def test_invite_expired_is_rejected(client, super_admin_token, db_conn):
    _, code = await _create_tenant_and_invite(client, super_admin_token)

    cur = db_conn.cursor()
    cur.execute("UPDATE invites SET expires_at = now() - interval '1 hour' WHERE code = %s", (code,))
    db_conn.commit()

    res = await client.post("/invite/accept", json={"code": code, "password": VALID_PASSWORD})
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_invite_accept_bad_password_strength(client, super_admin_token):
    _, code = await _create_tenant_and_invite(client, super_admin_token)
    # 8+ chars but no uppercase/special → passes schema, fails strength policy
    res = await client.post("/invite/accept", json={"code": code, "password": "12345678"})
    assert res.status_code == 400
    # Below min length → rejected by schema (422)
    res = await client.post("/invite/accept", json={"code": code, "password": "weak"})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_invite_accept_unknown_code(client):
    res = await client.post(
        "/invite/accept",
        json={"code": "A" * 43, "password": VALID_PASSWORD},
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_invite_accept_for_suspended_tenant(client, super_admin_token):
    tenant_id, code = await _create_tenant_and_invite(client, super_admin_token)
    await client.patch(
        f"/admin/tenants/{tenant_id}/suspend",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    res = await client.post("/invite/accept", json={"code": code, "password": VALID_PASSWORD})
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_no_further_invites_after_client_admin_exists(client, super_admin_token, db_conn):
    tenant_id, _ = await _create_tenant_and_invite(client, super_admin_token)

    # Simulate tenant already has a client admin
    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO users (tenant_id, email, password_hash, role) VALUES (%s,%s,%s,%s) RETURNING id",
        (tenant_id, "admin@nexus.io", "hash", "client_admin"),
    )
    db_conn.commit()

    res = await client.post(
        f"/admin/tenants/{tenant_id}/invite",
        json={"email": "third@nexus.io"},
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# Suspend / reactivate
# ---------------------------------------------------------------------------

async def _set_up_tenant_with_admin(client, super_admin_token):
    tenant_id, code = await _create_tenant_and_invite(client, super_admin_token)
    res = await client.post("/invite/accept", json={"code": code, "password": VALID_PASSWORD})
    assert res.status_code == 200
    return tenant_id


@pytest.mark.asyncio
async def test_suspend_blocks_login_and_revokes_sessions(client, super_admin_token):
    tenant_id = await _set_up_tenant_with_admin(client, super_admin_token)

    login = await client.post(
        "/auth/login",
        json={"organisation_code": "NEXUS", "email": "admin@nexus.io", "password": VALID_PASSWORD},
    )
    assert login.status_code == 200
    admin_session_token = login.json()["access_token"]

    res = await client.patch(
        f"/admin/tenants/{tenant_id}/suspend",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "suspended"

    # Pre-suspend session must stop working on the very next request
    res = await client.get("/documents", headers={"Authorization": f"Bearer {admin_session_token}"})
    assert res.status_code == 401

    # Fresh logins refused while suspended
    res = await client.post(
        "/auth/login",
        json={"organisation_code": "NEXUS", "email": "admin@nexus.io", "password": VALID_PASSWORD},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_reactivate_restores_login(client, super_admin_token):
    tenant_id = await _set_up_tenant_with_admin(client, super_admin_token)

    await client.patch(f"/admin/tenants/{tenant_id}/suspend", headers={"Authorization": f"Bearer {super_admin_token}"})
    res = await client.patch(
        f"/admin/tenants/{tenant_id}/reactivate",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "active"

    res = await client.post(
        "/auth/login",
        json={"organisation_code": "NEXUS", "email": "admin@nexus.io", "password": VALID_PASSWORD},
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_suspend_reactivate_state_machine(client, super_admin_token):
    tenant_id, _ = await _create_tenant_and_invite(client, super_admin_token)

    await client.patch(f"/admin/tenants/{tenant_id}/suspend", headers={"Authorization": f"Bearer {super_admin_token}"})
    res = await client.patch(
        f"/admin/tenants/{tenant_id}/suspend",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert res.status_code == 400

    res = await client.patch(
        f"/admin/tenants/{tenant_id}/reactivate",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert res.status_code == 200

    res = await client.patch(
        f"/admin/tenants/{tenant_id}/reactivate",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert res.status_code == 400

    res = await client.patch(
        f"/admin/tenants/{uuid.uuid4()}/suspend",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Audit trail completeness
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audit_records_lifecycle_actions(client, super_admin_token):
    tenant_id = await _set_up_tenant_with_admin(client, super_admin_token)
    await client.patch(f"/admin/tenants/{tenant_id}/suspend", headers={"Authorization": f"Bearer {super_admin_token}"})
    await client.patch(f"/admin/tenants/{tenant_id}/reactivate", headers={"Authorization": f"Bearer {super_admin_token}"})

    res = await client.get(
        f"/admin/tenants/{tenant_id}/audit",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert res.status_code == 200
    actions = {log["action"] for log in res.json()}
    assert {"create_tenant", "create_invite", "accept_invite", "suspend_tenant", "reactivate_tenant"} <= actions


# ---------------------------------------------------------------------------
# Permission enforcement on /admin endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_super_admin_denied_on_admin_endpoints(client, db_conn):
    cur = db_conn.cursor()
    cur.execute("INSERT INTO tenants (short_code, name, storage_quota_mb) VALUES (%s, %s, %s) RETURNING id", ("ZXQ", "Zqx", 2048))
    tenant_id = str(cur.fetchone()[0])
    db_conn.commit()

    user_id = seed_user(db_conn, "emp@zxq.com", "employee", tenant_id)
    token = make_token(db_conn, user_id, "employee", tenant_id)

    res = await client.get("/admin/tenants", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    res = await client.post(
        "/admin/tenants",
        json={"short_code": "ZZZ", "name": "Z"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    res = await client.patch(
        f"/admin/tenants/{tenant_id}/suspend",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_admin_endpoints_declared_super_admin_only_in_matrix():
    from app.auth.permissions import ROLE_MATRIX

    admin_entries = {k: v for k, v in ROLE_MATRIX.items() if k[1].startswith("/admin")}
    assert len(admin_entries) == 6
    assert all(v == {"super_admin"} for v in admin_entries.values())


# ---------------------------------------------------------------------------
# DB-level RLS: invites readable only via tenant context or exact code
# ---------------------------------------------------------------------------

def _seed_invite_policy_data(db_conn):
    cur = db_conn.cursor()
    cur.execute("INSERT INTO tenants (short_code, name, storage_quota_mb) VALUES (%s, %s, %s) RETURNING id", ("POLA", "Pol A", 2048))
    t1 = str(cur.fetchone()[0])
    cur.execute("INSERT INTO tenants (short_code, name, storage_quota_mb) VALUES (%s, %s, %s) RETURNING id", ("POLB", "Pol B", 2048))
    t2 = str(cur.fetchone()[0])

    cur.execute(
        "INSERT INTO users (tenant_id, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
        (t1, "poladmin@a.com", "hash", "client_admin"),
    )
    u1 = str(cur.fetchone()[0])

    code1 = "code_tenant_a_00000000000000000001"
    code2 = "code_tenant_b_00000000000000000002"
    cur.execute(
        "INSERT INTO invites (tenant_id, email, code, expires_at, created_by) VALUES (%s,%s,%s, now() + interval '7 days', %s)",
        (t1, "admin@a.com", code1, u1),
    )
    cur.execute(
        "INSERT INTO invites (tenant_id, email, code, expires_at, created_by) VALUES (%s,%s,%s, now() + interval '7 days', %s)",
        (t2, "admin@b.com", code2, u1),
    )
    db_conn.commit()
    return t1, t2, code1, code2


def _app_url():
    return settings.DATABASE_URL_SYNC.replace("vaultiq:vaultiq_secret", "vaultiq_app:vaultiq_secret")


def test_invites_rls_tenant_context_only(db_conn):
    t1, t2, code1, code2 = _seed_invite_policy_data(db_conn)
    conn = psycopg2.connect(_app_url())
    cur = conn.cursor()

    cur.execute("SELECT set_config('app.current_tenant', %s, true)", (t1,))
    cur.execute("SELECT code FROM invites")
    codes = [r[0] for r in cur.fetchall()]
    assert code1 in codes and code2 not in codes, "Tenant A saw Tenant B's invite"

    cur.execute("SELECT set_config('app.current_tenant', %s, true)", (t2,))
    cur.execute("SELECT code FROM invites")
    codes = [r[0] for r in cur.fetchall()]
    assert code1 not in codes and code2 in codes

    cur.close()
    conn.close()


def test_invites_rls_code_lookup_without_tenant_context(db_conn):
    t1, t2, code1, code2 = _seed_invite_policy_data(db_conn)
    conn = psycopg2.connect(_app_url())
    cur = conn.cursor()

    cur.execute("SELECT set_config('app.invite_accept_code', %s, true)", (code1,))
    cur.execute("SELECT code FROM invites")
    codes = [r[0] for r in cur.fetchall()]
    assert codes == [code1], f"Code lookup should return exactly the invite, got {codes}"

    cur.execute("SELECT set_config('app.invite_accept_code', %s, true)", ("no_such_code_00000000000000",))
    cur.execute("SELECT code FROM invites")
    assert cur.fetchall() == []

    cur.close()
    conn.close()


def test_invites_insert_requires_tenant_context(db_conn):
    t1, t2, code1, code2 = _seed_invite_policy_data(db_conn)
    conn = psycopg2.connect(_app_url())
    cur = conn.cursor()

    cur.execute("SELECT set_config('app.invite_accept_code', %s, true)", (code1,))
    try:
        cur.execute(
            "INSERT INTO invites (tenant_id, email, code, expires_at, created_by) "
            "VALUES (%s, 'x@x.com', 'brand_new_code_000000000000000001', now() + interval '1 day', %s)",
            (t1, uuid.uuid4()),
        )
        conn.commit()
        pytest.fail("INSERT without tenant context should be blocked by RLS")
    except psycopg2.Error:
        conn.rollback()
    finally:
        cur.close()
        conn.close()


def test_audit_actor_role_free_text(db_conn):
    """accept_invite writes actor_role='system' — column must accept non-enum values."""
    t1, t2, code1, code2 = _seed_invite_policy_data(db_conn)
    cur = db_conn.cursor()
    target_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO audit_logs (tenant_id, actor_user_id, actor_role, action, target_type, target_id, details) "
        "VALUES (%s, NULL, 'system', 'accept_invite', 'user', %s, '{}')",
        (t1, target_id),
    )
    db_conn.commit()
    cur.execute("SELECT actor_role FROM audit_logs WHERE action='accept_invite'")
    assert cur.fetchone()[0] == "system"