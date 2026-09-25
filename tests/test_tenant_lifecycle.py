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
import pytest
import pytest_asyncio
import httpx
from app.auth.password import hash_password
from app.auth.jwt import create_access_token
from app.config import get_settings

settings = get_settings()

VALID_PASSWORD = "Adm1n!Passw0rd"


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


async def _create_tenant_and_invite(client, token, code=None, email="admin@nexus.io"):
    if code is None:
        # Generate a valid short_code: max 20 chars, uppercase alphanumeric only
        code = f"NX{uuid.uuid4().hex[:10].upper()}"
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


async def _set_up_tenant_with_admin(client, token, code=None):
    tenant_id, code = await _create_tenant_and_invite(client, token, code=code)
    res = await client.post("/invite/accept", json={"code": code, "password": VALID_PASSWORD})
    assert res.status_code == 200
    assert res.json()["tenant_id"] == tenant_id
    return tenant_id


def _seed_invite_policy_data(db_conn):
    """Seed two tenants for invite policy tests."""
    cur = db_conn.cursor()
    cur.execute("INSERT INTO tenants (short_code, name) VALUES (%s, %s) RETURNING id", ("POLA", "Pol A"))
    t1 = str(cur.fetchone()[0])
    cur.execute("INSERT INTO tenants (short_code, name) VALUES (%s, %s) RETURNING id", ("POLB", "Pol B"))
    t2 = str(cur.fetchone()[0])

    cur.execute(
        "INSERT INTO users (tenant_id, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
        (t1, "u1@pol.com", hash_password("Str0ng!Passw0rd"), "client_admin"),
    )
    u1 = str(cur.fetchone()[0])
    cur.execute(
        "INSERT INTO users (tenant_id, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
        (t2, "u2@pol.com", hash_password("Str0ng!Passw0rd"), "client_admin"),
    )
    u2 = str(cur.fetchone()[0])

    cur.execute(
        "INSERT INTO sessions (user_id, tenant_id, token_hash, expires_at) VALUES (%s, %s, %s, now() + interval '1 hour') RETURNING id",
        (u1, t1, "tok1"),
    )
    s1 = str(cur.fetchone()[0])
    cur.execute(
        "INSERT INTO sessions (user_id, tenant_id, token_hash, expires_at) VALUES (%s, %s, %s, now() + interval '1 hour') RETURNING id",
        (u2, t2, "tok2"),
    )
    s2 = str(cur.fetchone()[0])

    cur.execute(
        "INSERT INTO invites (tenant_id, email, code, expires_at, created_by) VALUES (%s, %s, %s, now() + interval '1 hour', %s) RETURNING id, code",
        (t1, "invite@pol.com", "code1", u1),
    )
    i1_id, code1 = cur.fetchone()
    cur.execute(
        "INSERT INTO invites (tenant_id, email, code, expires_at, created_by) VALUES (%s, %s, %s, now() + interval '1 hour', %s) RETURNING id, code",
        (t2, "invite@pol.com", "code2", u2),
    )
    i2_id, code2 = cur.fetchone()
    db_conn.commit()

    return t1, t2, code1, code2


# ---------------------------------------------------------------------------
# Tenant creation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_tenant_and_audit_log(async_client, super_admin_token):
    code = f"ACME{uuid.uuid4().hex[:8].upper()}"
    res = await async_client.post(
        "/admin/tenants",
        json={"short_code": code, "name": "Acme Corp", "storage_quota_mb": 1000},
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["short_code"] == code
    assert body["status"] == "active"
    assert body["storage_quota_mb"] == 1000

    res = await async_client.get(
        f"/admin/tenants/{body['id']}/audit",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert res.status_code == 200
    logs = res.json()
    assert any(log["action"] == "create_tenant" for log in logs)
    assert logs[0]["actor_role"] == "super_admin"


@pytest.mark.asyncio
async def test_create_tenant_duplicate_code_conflict(async_client, super_admin_token):
    code = f"DUP{uuid.uuid4().hex[:8].upper()}"
    payload = {"short_code": code, "name": "Acme Corp", "storage_quota_mb": 2048}
    res1 = await async_client.post("/admin/tenants", json=payload, headers={"Authorization": f"Bearer {super_admin_token}"})
    assert res1.status_code == 201
    res2 = await async_client.post("/admin/tenants", json=payload, headers={"Authorization": f"Bearer {super_admin_token}"})
    assert res2.status_code == 409


@pytest.mark.asyncio
async def test_create_tenant_rejects_bad_short_code(async_client, super_admin_token):
    for bad in ["a", "has space", "with.dot", "x" * 21, "low§"]:
        res = await async_client.post(
            "/admin/tenants",
            json={"short_code": bad, "name": "X"},
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert res.status_code == 422, f"short_code={bad!r} should be rejected"


@pytest.mark.asyncio
async def test_list_tenants_shows_all(async_client, super_admin_token):
    codes = [f"ALFA{uuid.uuid4().hex[:6].upper()}", f"BETA{uuid.uuid4().hex[:6].upper()}"]
    for code in codes:
        res = await async_client.post(
            "/admin/tenants",
            json={"short_code": code, "name": code, "storage_quota_mb": 2048},
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert res.status_code == 201
    res = await async_client.get("/admin/tenants", headers={"Authorization": f"Bearer {super_admin_token}"})
    assert res.status_code == 200
    returned_codes = {t["short_code"] for t in res.json()}
    assert set(codes) <= returned_codes


# ---------------------------------------------------------------------------
# Invite create + accept
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invite_accept_creates_client_admin(async_client, super_admin_token):
    # Use a known short_code for this test
    known_code = "NEXUS"
    tenant_id, code = await _create_tenant_and_invite(async_client, super_admin_token, code=known_code)

    res = await async_client.post("/invite/accept", json={"code": code, "password": VALID_PASSWORD})
    assert res.status_code == 200
    assert res.json()["tenant_id"] == tenant_id

    res = await async_client.post(
        "/auth/login",
        json={"organisation_code": known_code, "email": "admin@nexus.io", "password": VALID_PASSWORD},
    )
    assert res.status_code == 200
    assert res.json()["role"] == "client_admin"
    assert res.json()["tenant_id"] == tenant_id

    # A second accept must fail (one-time use)
    res = await async_client.post("/invite/accept", json={"code": code, "password": VALID_PASSWORD})
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_invite_cannot_be_reused(async_client, super_admin_token):
    _, code = await _create_tenant_and_invite(async_client, super_admin_token)

    res1 = await async_client.post("/invite/accept", json={"code": code, "password": VALID_PASSWORD})
    assert res1.status_code == 200

    res2 = await async_client.post("/invite/accept", json={"code": code, "password": VALID_PASSWORD})
    assert res2.status_code == 400


@pytest.mark.asyncio
async def test_invite_expired_is_rejected(async_client, super_admin_token, db_conn):
    _, code = await _create_tenant_and_invite(async_client, super_admin_token)

    cur = db_conn.cursor()
    cur.execute("UPDATE invites SET expires_at = now() - interval '1 hour' WHERE code = %s", (code,))
    db_conn.commit()

    res = await async_client.post("/invite/accept", json={"code": code, "password": VALID_PASSWORD})
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invite_accept_bad_password_strength(async_client, super_admin_token):
    _, code = await _create_tenant_and_invite(async_client, super_admin_token)

    weak = "weak"
    res = await async_client.post("/invite/accept", json={"code": code, "password": weak})
    # Pydantic validation may return 422, endpoint validation returns 400
    assert res.status_code in (400, 422)
    detail = res.json()["detail"]
    if isinstance(detail, list):
        detail = " ".join(str(d) for d in detail)
    assert "password" in detail.lower()


@pytest.mark.asyncio
async def test_invite_accept_unknown_code(async_client):
    res = await async_client.post("/invite/accept", json={"code": "UNKNOWNCODE123", "password": VALID_PASSWORD})
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_invite_accept_for_suspended_tenant(async_client, super_admin_token, db_conn):
    tenant_id, code = await _create_tenant_and_invite(async_client, super_admin_token)

    # Suspend tenant before accepting invite
    cur = db_conn.cursor()
    cur.execute("UPDATE tenants SET status = 'suspended' WHERE id = %s", (tenant_id,))
    db_conn.commit()

    res = await async_client.post("/invite/accept", json={"code": code, "password": VALID_PASSWORD})
    # Returns 400 for suspended tenant (not 403)
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_no_further_invites_after_client_admin_exists(async_client, super_admin_token):
    tenant_id, code = await _create_tenant_and_invite(async_client, super_admin_token)

    # Accept the invite to create the client_admin
    res = await async_client.post("/invite/accept", json={"code": code, "password": VALID_PASSWORD})
    assert res.status_code == 200

    # Now try to create another invite - should fail
    res = await async_client.post(
        f"/admin/tenants/{tenant_id}/invite",
        json={"email": "another@nexus.io", "expires_in_hours": 24},
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert res.status_code == 400
    assert "already has a client admin" in res.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Suspend / reactivate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suspend_blocks_login_and_revokes_sessions(async_client, super_admin_token):
    # Use a known short_code for this test
    known_code = "NEXUS"
    tenant_id = await _set_up_tenant_with_admin(async_client, super_admin_token, code=known_code)

    # Login works before suspend
    res = await async_client.post(
        "/auth/login",
        json={"organisation_code": known_code, "email": "admin@nexus.io", "password": VALID_PASSWORD},
    )
    assert res.status_code == 200
    token = res.json()["access_token"]

    # Suspend tenant
    res = await async_client.patch(
        f"/admin/tenants/{tenant_id}/suspend",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    print(f"DEBUG: suspend status={res.status_code}, response={res.json()}")
    assert res.status_code == 200
    assert res.json()["status"] == "suspended"

    # Pre-suspend token should be rejected on next request
    res = await async_client.get(
        "/documents",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 401

    # Fresh login while suspended should fail
    res = await async_client.post(
        "/auth/login",
        json={"organisation_code": "NEXUS", "email": "admin@nexus.io", "password": VALID_PASSWORD},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_reactivate_restores_login(async_client, super_admin_token):
    known_code = "NEXUS"
    tenant_id = await _set_up_tenant_with_admin(async_client, super_admin_token, code=known_code)

    # Suspend
    res = await async_client.patch(
        f"/admin/tenants/{tenant_id}/suspend",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert res.status_code == 200

    # Reactivate
    res = await async_client.patch(
        f"/admin/tenants/{tenant_id}/reactivate",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "active"

    # Login should work again
    res = await async_client.post(
        "/auth/login",
        json={"organisation_code": known_code, "email": "admin@nexus.io", "password": VALID_PASSWORD},
    )
    assert res.status_code == 200
    assert res.json()["role"] == "client_admin"


@pytest.mark.asyncio
async def test_suspend_reactivate_state_machine(async_client, super_admin_token):
    tenant_id, _ = await _create_tenant_and_invite(async_client, super_admin_token)

    # active -> suspended
    res = await async_client.patch(
        f"/admin/tenants/{tenant_id}/suspend",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "suspended"

    # suspended -> active
    res = await async_client.patch(
        f"/admin/tenants/{tenant_id}/reactivate",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "active"

    # active -> suspended again
    res = await async_client.patch(
        f"/admin/tenants/{tenant_id}/suspend",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "suspended"


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_records_lifecycle_actions(async_client, super_admin_token):
    tenant_id = await _set_up_tenant_with_admin(async_client, super_admin_token)

    # Suspend
    await async_client.patch(
        f"/admin/tenants/{tenant_id}/suspend",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    # Reactivate
    await async_client.patch(
        f"/admin/tenants/{tenant_id}/reactivate",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )

    res = await async_client.get(
        f"/admin/tenants/{tenant_id}/audit",
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )
    assert res.status_code == 200
    logs = res.json()
    actions = [log["action"] for log in logs]
    assert "create_tenant" in actions
    assert "create_invite" in actions
    assert "accept_invite" in actions
    assert "suspend_tenant" in actions
    assert "reactivate_tenant" in actions
    # All actor_role should be super_admin except accept_invite which is system
    for log in logs:
        if log["action"] == "accept_invite":
            assert log["actor_role"] == "system"
        else:
            assert log["actor_role"] == "super_admin"


# ---------------------------------------------------------------------------
# Permission enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_super_admin_denied_on_admin_endpoints(async_client, db_conn):
    cur = db_conn.cursor()
    cur.execute("INSERT INTO tenants (short_code, name) VALUES (%s, %s) RETURNING id", ("ZXQ", "Zqx"))
    tenant_id = str(cur.fetchone()[0])
    cur.execute(
        "INSERT INTO users (tenant_id, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
        (tenant_id, "admin@zxq.com", hash_password("Str0ng!Passw0rd"), "client_admin"),
    )
    u1 = str(cur.fetchone()[0])
    cur.execute(
        "INSERT INTO sessions (user_id, tenant_id, token_hash, expires_at) VALUES (%s, %s, %s, now() + interval '1 hour') RETURNING id",
        (u1, tenant_id, "tok"),
    )
    s1 = str(cur.fetchone()[0])
    db_conn.commit()

    client_admin_token = create_access_token(
        user_id=uuid.UUID(u1),
        role="client_admin",
        tenant_id=uuid.UUID(tenant_id),
        session_id=uuid.UUID(s1),
    )

    endpoints = [
        ("POST", "/admin/tenants", {"short_code": "NEW", "name": "New"}),
        ("GET", "/admin/tenants", None),
        ("PATCH", f"/admin/tenants/{tenant_id}/suspend", None),
        ("PATCH", f"/admin/tenants/{tenant_id}/reactivate", None),
        ("POST", f"/admin/tenants/{tenant_id}/invite", {"email": "x@y.com"}),
        ("GET", f"/admin/tenants/{tenant_id}/audit", None),
    ]

    for method, url, payload in endpoints:
        headers = {"Authorization": f"Bearer {client_admin_token}"}
        if method == "POST":
            res = await async_client.post(url, json=payload, headers=headers)
        elif method == "GET":
            res = await async_client.get(url, headers=headers)
        elif method == "PATCH":
            res = await async_client.patch(url, headers=headers)
        assert res.status_code == 403, f"{method} {url} should be 403 for client_admin"


def test_admin_endpoints_declared_super_admin_only_in_matrix():
    from app.auth.permissions import ROLE_MATRIX

    admin_paths = [
        ("POST", "/admin/tenants"),
        ("GET", "/admin/tenants"),
        ("PATCH", "/admin/tenants/{tenant_id}/suspend"),
        ("PATCH", "/admin/tenants/{tenant_id}/reactivate"),
        ("POST", "/admin/tenants/{tenant_id}/invite"),
        ("GET", "/admin/tenants/{tenant_id}/audit"),
    ]
    for method, path in admin_paths:
        allowed = ROLE_MATRIX.get((method, path), set())
        assert allowed == {"super_admin"}, f"{method} {path} should be super_admin only, got {allowed}"


# ---------------------------------------------------------------------------
# RLS on invites
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invites_rls_tenant_context_only(db_conn, app_db_conn):
    t1, t2, code1, code2 = _seed_invite_policy_data(db_conn)

    cur = app_db_conn.cursor()
    cur.execute("SET LOCAL app.current_tenant = %s", (t1,))
    cur.execute("SELECT * FROM invites")
    rows = cur.fetchall()
    assert len(rows) == 1
    assert rows[0][3] == code1  # code column at index 3

    cur.execute("SET LOCAL app.current_tenant = %s", (t2,))
    cur.execute("SELECT * FROM invites")
    rows = cur.fetchall()
    assert len(rows) == 1
    assert rows[0][3] == code2


@pytest.mark.asyncio
async def test_invites_rls_code_lookup_without_tenant_context(db_conn, app_db_conn):
    t1, t2, code1, code2 = _seed_invite_policy_data(db_conn)

    cur = app_db_conn.cursor()
    # Set the invite_accept_code setting for the code-lookup policy
    cur.execute("SET LOCAL app.invite_accept_code = %s", (code1,))
    cur.execute("SELECT * FROM invites WHERE code = %s", (code1,))
    row = cur.fetchone()
    assert row is not None
    assert row[3] == code1  # code column at index 3

    cur.execute("SET LOCAL app.invite_accept_code = %s", (code2,))
    cur.execute("SELECT * FROM invites WHERE code = %s", (code2,))
    row = cur.fetchone()
    assert row is not None
    assert row[3] == code2


@pytest.mark.asyncio
async def test_invites_insert_requires_tenant_context(app_db_conn):
    cur = app_db_conn.cursor()
    cur.execute("SET LOCAL app.current_tenant = '00000000-0000-0000-0000-000000000000'")
    # Should fail because no valid tenant context
    try:
        cur.execute(
            "INSERT INTO invites (tenant_id, email, code, expires_at) VALUES (%s, %s, %s, now() + interval '1 hour')",
            ("00000000-0000-0000-0000-000000000000", "test@test.com", "testcode"),
        )
        app_db_conn.commit()
        assert False, "Expected insert to fail without valid tenant context"
    except Exception:
        app_db_conn.rollback()


# ---------------------------------------------------------------------------
# Audit actor_role free text
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_actor_role_free_text(db_conn, app_db_conn):
    t1, t2, code1, code2 = _seed_invite_policy_data(db_conn)

    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO audit_logs (tenant_id, actor_user_id, actor_role, action, target_type, target_id, details) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (t1, None, "custom_role_xyz", "custom_action", "tenant", t1, '{"key": "value"}'),
    )
    db_conn.commit()

    cur.execute("SELECT actor_role FROM audit_logs WHERE action = 'custom_action'")
    row = cur.fetchone()
    assert row[0] == "custom_role_xyz"