"""VQ-402: Audit trail, compliance export, retention.

Must-prove items from the story:
1. The application identity (vaultiq_app) cannot modify audit rows
2. Retention only touches one tenant
3. Ten actions performed -> the export contains all ten
"""
import csv
import io
import json
from datetime import datetime, timezone

import psycopg2
import pytest

from app.config import get_settings

settings = get_settings()


def get_app_connection():
    app_url = settings.DATABASE_URL_SYNC.replace(
        "vaultiq:vaultiq_secret", "vaultiq_app:vaultiq_secret"
    )
    return psycopg2.connect(app_url)


def _seed_tenant(conn, code, retention_days=365):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tenants (short_code, name, retention_days) VALUES (%s, %s, %s) RETURNING id",
        (code, f"Tenant {code}", retention_days),
    )
    tenant_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    return tenant_id


def _seed_audit(conn, tenant_id, action, age_days=None, details=None):
    tenant_id = str(tenant_id)
    cur = conn.cursor()
    if age_days is None:
        cur.execute(
            "INSERT INTO audit_logs (tenant_id, actor_role, action, target_type, target_id, details) "
            "VALUES (%s, 'system', %s, 'tenant', %s, %s) RETURNING id",
            (tenant_id, action, tenant_id, json.dumps(details or {})),
        )
    else:
        cur.execute(
            "INSERT INTO audit_logs (tenant_id, actor_role, action, target_type, target_id, details, created_at) "
            "VALUES (%s, 'system', %s, 'tenant', %s, %s, now() - make_interval(days => %s)) RETURNING id",
            (tenant_id, action, tenant_id, json.dumps(details or {}), age_days),
        )
    row_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    return row_id


def _audit_actions(rows):
    return {row["action"] for row in rows}


def _parse_csv(content: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(content)))


# ---------------------------------------------------------------------------
# 1. Audit rows cannot be edited or deleted by the application identity
# ---------------------------------------------------------------------------

class TestAuditImmutability:
    """AC2: audit records cannot be edited or deleted by the application."""

    def test_app_identity_cannot_update_audit_rows(self, db_conn, app_db_conn):
        tenant_id = _seed_tenant(conn=db_conn, code="IMMU1")
        _seed_audit(db_conn, tenant_id, "original_action")

        cur = app_db_conn.cursor()
        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (str(tenant_id),))

        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute("UPDATE audit_logs SET action = 'tampered'")
        app_db_conn.rollback()

        cur = app_db_conn.cursor()
        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (str(tenant_id),))
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute("DELETE FROM audit_logs")
        app_db_conn.rollback()

        # Row is untouched
        cur = db_conn.cursor()
        cur.execute("SELECT action FROM audit_logs WHERE tenant_id = %s", (tenant_id,))
        actions = [r[0] for r in cur.fetchall()]
        assert actions == ["original_action"], f"Row was modified: {actions}"
        cur.close()

    def test_app_identity_cannot_delete_specific_audit_row(self, db_conn, app_db_conn):
        tenant_id = _seed_tenant(conn=db_conn, code="IMMU2")
        row_id = _seed_audit(db_conn, tenant_id, "protected_action")

        cur = app_db_conn.cursor()
        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (str(tenant_id),))
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute("DELETE FROM audit_logs WHERE id = %s", (row_id,))
        app_db_conn.rollback()

        cur = db_conn.cursor()
        cur.execute("SELECT count(*) FROM audit_logs WHERE id = %s", (row_id,))
        assert cur.fetchone()[0] == 1
        cur.close()

    def test_app_identity_can_insert_and_select_audit_rows(self, db_conn, app_db_conn):
        """Positive control: the trail still works for the app identity."""
        tenant_id = _seed_tenant(conn=db_conn, code="IMMU3")

        cur = app_db_conn.cursor()
        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (str(tenant_id),))
        cur.execute(
            "INSERT INTO audit_logs (tenant_id, actor_role, action, target_type, target_id, details) "
            "VALUES (%s, 'client_admin', 'allowed_action', 'tenant', %s, '{}')",
            (tenant_id, tenant_id),
        )
        app_db_conn.commit()

        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (str(tenant_id),))
        cur.execute("SELECT action FROM audit_logs WHERE tenant_id = %s", (tenant_id,))
        rows = cur.fetchall()
        assert [r[0] for r in rows] == ["allowed_action"]
        cur.close()

    def test_vaultiq_app_holds_only_select_insert_on_audit_logs(self, db_conn):
        """DB-level proof: no UPDATE/DELETE grant exists for the app identity."""
        cur = db_conn.cursor()
        cur.execute(
            "SELECT privilege_type FROM information_schema.role_table_grants "
            "WHERE grantee = 'vaultiq_app' AND table_name = 'audit_logs'"
        )
        privileges = {row[0] for row in cur.fetchall()}
        cur.close()
        assert privileges == {"SELECT", "INSERT"}, (
            f"vaultiq_app audit_logs privileges changed: {sorted(privileges)}"
        )


# ---------------------------------------------------------------------------
# 2. Retention only touches one tenant
# ---------------------------------------------------------------------------

class TestRetention:
    """AC4: records older than the tenant's retention period are removed
    per tenant, never across tenants."""

    def test_purge_touches_only_the_requested_tenants_old_rows(
        self, db_conn, app_db_conn
    ):
        tenant_a = _seed_tenant(db_conn, "RETA", retention_days=30)
        tenant_b = _seed_tenant(db_conn, "RETB", retention_days=365)

        a_old = _seed_audit(db_conn, tenant_a, "a_old", age_days=100)
        a_recent = _seed_audit(db_conn, tenant_a, "a_recent", age_days=5)
        b_old = _seed_audit(db_conn, tenant_b, "b_old", age_days=100)
        b_recent = _seed_audit(db_conn, tenant_b, "b_recent", age_days=5)

        # Run the purge as the application identity (the granted path)
        cur = app_db_conn.cursor()
        cur.execute(
            "SELECT table_name, rows_deleted FROM vaultiq_purge_tenant_retention(%s)",
            (str(tenant_a),),
        )
        results = dict(cur.fetchall())
        app_db_conn.commit()
        cur.close()

        assert results["audit_logs"] == 1, f"Expected 1 purged row, got {results}"

        cur = db_conn.cursor()
        surviving = set()
        cur.execute("SELECT id FROM audit_logs")
        for row in cur.fetchall():
            surviving.add(row[0])
        cur.close()

        assert a_old not in surviving, "Tenant A's expired row must be purged"
        assert a_recent in surviving, "Tenant A's recent row must survive"
        assert b_old in surviving, "Tenant B's expired row must NOT be purged"
        assert b_recent in surviving, "Tenant B's recent row must NOT be purged"

    @pytest.mark.asyncio
    async def test_retention_job_purges_per_tenant(self, db_conn):
        from app.retention import run_retention_once

        tenant_a = _seed_tenant(db_conn, "JOBA", retention_days=1)
        tenant_b = _seed_tenant(db_conn, "JOBB", retention_days=365)

        a_expired = _seed_audit(db_conn, tenant_a, "a_expired", age_days=10)
        a_fresh = _seed_audit(db_conn, tenant_a, "a_fresh", age_days=0)
        b_expired = _seed_audit(db_conn, tenant_b, "b_expired", age_days=10)

        results = await run_retention_once()
        by_code = {entry["short_code"]: entry for entry in results}

        assert by_code["JOBA"]["purged"]["audit_logs"] == 1
        assert by_code["JOBB"]["purged"]["audit_logs"] == 0
        assert by_code["JOBA"]["retention_days"] == 1
        assert by_code["JOBB"]["retention_days"] == 365

        cur = db_conn.cursor()
        cur.execute("SELECT id FROM audit_logs")
        surviving = {row[0] for row in cur.fetchall()}
        cur.close()

        assert a_expired not in surviving, "Job must purge tenant A's expired row"
        assert a_fresh in surviving, "Job must keep tenant A's fresh row"
        assert b_expired in surviving, "Job must not cross into tenant B"

    @pytest.mark.asyncio
    async def test_retention_job_handles_empty_database(self, db_conn):
        from app.retention import run_retention_once

        results = await run_retention_once()
        assert results == []


# ---------------------------------------------------------------------------
# 3. Export: recording, range, roles, isolation
# ---------------------------------------------------------------------------

class TestAuditExport:
    """AC3: Client Admin can export their tenant's trail for a date range;
    the export itself is recorded."""

    @pytest.mark.asyncio
    async def test_export_records_itself(
        self, async_client, token_a_admin, tenant_a
    ):
        resp = await async_client.get(
            "/audit/export",
            headers={"Authorization": f"Bearer {token_a_admin}"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"].startswith("text/csv")
        assert "attachment" in resp.headers["content-disposition"]

        rows = _parse_csv(resp.text)
        assert len(rows) == 1, f"Expected only the export's own row, got {rows}"
        assert rows[0]["action"] == "export_audit"
        assert rows[0]["tenant_id"] == str(tenant_a["id"])

        # A second export must contain the first export's record (self-including)
        resp2 = await async_client.get(
            "/audit/export",
            headers={"Authorization": f"Bearer {token_a_admin}"},
        )
        rows2 = _parse_csv(resp2.text)
        assert len(rows2) == 2
        assert rows[0]["id"] in {r["id"] for r in rows2}, (
            "Export must contain its own earlier export record"
        )

    @pytest.mark.asyncio
    async def test_export_json_format(self, async_client, token_a_admin):
        resp = await async_client.get(
            "/audit/export?format=json",
            headers={"Authorization": f"Bearer {token_a_admin}"},
        )
        assert resp.status_code == 200, resp.text
        rows = resp.json()
        assert isinstance(rows, list)
        assert rows[0]["action"] == "export_audit"

    @pytest.mark.asyncio
    async def test_export_date_range_filters(self, async_client, db_conn, token_a_admin, tenant_a):
        old_id = _seed_audit(
            db_conn, tenant_a["id"], "old_row", age_days=10,
            details={"mark": "outside_range"},
        )
        today = datetime.now(timezone.utc).date().isoformat()

        resp = await async_client.get(
            f"/audit/export?format=json&start_date={today}&end_date={today}",
            headers={"Authorization": f"Bearer {token_a_admin}"},
        )
        assert resp.status_code == 200, resp.text
        rows = resp.json()
        ids = {row["id"] for row in rows}
        assert str(old_id) not in ids, "Row outside the date range must be excluded"
        assert all(row["action"] == "export_audit" for row in rows)

        # Backdated row is inside a wide range
        resp = await async_client.get(
            "/audit/export?format=json&start_date=2020-01-01",
            headers={"Authorization": f"Bearer {token_a_admin}"},
        )
        assert str(old_id) in {row["id"] for row in resp.json()}

    @pytest.mark.asyncio
    async def test_export_invalid_date_range_rejected(self, async_client, token_a_admin):
        resp = await async_client.get(
            "/audit/export?start_date=2026-10-02&end_date=2026-10-01",
            headers={"Authorization": f"Bearer {token_a_admin}"},
        )
        assert resp.status_code == 400
        assert "start_date" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_export_denied_for_employee(self, async_client, token_a_emp):
        resp = await async_client.get(
            "/audit/export",
            headers={"Authorization": f"Bearer {token_a_emp}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_export_denied_for_super_admin(
        self, async_client, super_admin_token, tenant_a
    ):
        """Super Admin has no tenant to export for via this path."""
        resp = await async_client.get(
            "/audit/export",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_export_requires_authentication(self, async_client):
        resp = await async_client.get("/audit/export")
        assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_export_contains_no_other_tenants_rows(
        self, async_client, db_conn, token_a_admin, tenant_a, tenant_b
    ):
        _seed_audit(
            db_conn, tenant_a["id"], "a_row", details={"mark": "a_marker"}
        )
        b_row = _seed_audit(
            db_conn, tenant_b["id"], "b_row", details={"mark": "b_secret_marker"}
        )

        resp = await async_client.get(
            "/audit/export",
            headers={"Authorization": f"Bearer {token_a_admin}"},
        )
        assert resp.status_code == 200
        body = resp.text
        assert "b_secret_marker" not in body, "Export leaked tenant B content"
        assert str(tenant_b["id"]) not in body, "Export leaked tenant B id"
        assert "TENANT_B" not in body.upper(), "Export leaked tenant B short code"
        assert str(b_row) not in body, "Export leaked tenant B audit row id"

        rows = _parse_csv(body)
        assert rows, "Expected tenant A's rows"
        assert all(row["tenant_id"] == str(tenant_a["id"]) for row in rows)

    @pytest.mark.asyncio
    async def test_no_write_method_exists_on_audit_routes(
        self, async_client, super_admin_token, token_a_admin, tenant_a
    ):
        """There is no API path to edit or delete trail rows."""
        auth = {"Authorization": f"Bearer {token_a_admin}"}
        for method in ("POST", "PATCH", "PUT", "DELETE"):
            resp = await getattr(async_client, method.lower())("/audit/export", headers=auth)
            assert resp.status_code == 405, (
                f"{method} /audit/export should be method-not-allowed, got {resp.status_code}"
            )

        admin_auth = {"Authorization": f"Bearer {super_admin_token}"}
        for method in ("POST", "PATCH", "PUT", "DELETE"):
            resp = await getattr(async_client, method.lower())(
                f"/admin/tenants/{tenant_a['id']}/audit", headers=admin_auth
            )
            assert resp.status_code == 405, (
                f"{method} /admin/tenants/{{id}}/audit should be method-not-allowed, got {resp.status_code}"
            )


# ---------------------------------------------------------------------------
# 4. The actions themselves are recorded
# ---------------------------------------------------------------------------

class TestRecordedActions:
    """AC1: login, logout, failed login, upload, delete land on the trail."""

    @pytest.mark.asyncio
    async def test_login_logout_and_failed_login_recorded(
        self, async_client, token_a_admin, tenant_a
    ):
        login_body = {
            "organisation_code": "TENANT_A",
            "email": tenant_a["client_admin"]["email"],
            "password": "StrongPass1!",
        }

        # Failed login (wrong password)
        resp = await async_client.post(
            "/auth/login", json={**login_body, "password": "WrongPass1!"}
        )
        assert resp.status_code == 401

        # Successful login
        resp = await async_client.post("/auth/login", json=login_body)
        assert resp.status_code == 200, resp.text
        login_token = resp.json()["access_token"]

        # Logout with the session created by that login
        resp = await async_client.post(
            "/auth/logout", headers={"Authorization": f"Bearer {login_token}"}
        )
        assert resp.status_code == 200

        # Export as the tenant's client admin
        resp = await async_client.get(
            "/audit/export?format=json",
            headers={"Authorization": f"Bearer {token_a_admin}"},
        )
        assert resp.status_code == 200, resp.text
        rows = resp.json()
        actions = _audit_actions(rows)
        assert "failed_login" in actions, f"Missing failed_login; have {sorted(actions)}"
        assert "login" in actions, f"Missing login; have {sorted(actions)}"
        assert "logout" in actions, f"Missing logout; have {sorted(actions)}"

        failed = [r for r in rows if r["action"] == "failed_login"]
        assert failed, "Expected a failed_login row"
        details = json.loads(failed[0]["details"])
        assert details["reason"] == "wrong_password"

    @pytest.mark.asyncio
    async def test_unknown_email_for_known_org_is_recorded(
        self, async_client, token_a_admin, tenant_a
    ):
        resp = await async_client.post(
            "/auth/login",
            json={
                "organisation_code": "TENANT_A",
                "email": "nobody@nowhere.com",
                "password": "Whatever1!",
            },
        )
        assert resp.status_code == 401

        resp = await async_client.get(
            "/audit/export?format=json",
            headers={"Authorization": f"Bearer {token_a_admin}"},
        )
        rows = resp.json()
        failed = [r for r in rows if r["action"] == "failed_login"]
        assert failed, "Unknown email for a known org must be recorded"
        assert json.loads(failed[0]["details"])["reason"] == "unknown_email"

    @pytest.mark.asyncio
    async def test_upload_and_delete_recorded(self, async_client, token_a_admin):
        headers = {"Authorization": f"Bearer {token_a_admin}"}
        resp = await async_client.post(
            "/documents",
            files={"file": ("audit_target.txt", io.BytesIO(b"content"), "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 201, resp.text
        doc_id = resp.json()["id"]

        resp = await async_client.delete(f"/documents/{doc_id}", headers=headers)
        assert resp.status_code == 204

        resp = await async_client.get("/audit/export?format=json", headers=headers)
        rows = resp.json()
        actions = _audit_actions(rows)
        assert "upload_document" in actions, f"Missing upload; have {sorted(actions)}"
        assert "delete_document" in actions, f"Missing delete; have {sorted(actions)}"

        upload_row = next(r for r in rows if r["action"] == "upload_document")
        assert json.loads(upload_row["details"])["filename"] == "audit_target.txt"


# ---------------------------------------------------------------------------
# 5. Ten actions performed -> the export contains all ten (live-evidence twin)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_export_contains_all_ten_performed_actions(async_client, super_admin_token):
    admin = {"Authorization": f"Bearer {super_admin_token}"}

    # 1. create_tenant
    resp = await async_client.post(
        "/admin/tenants",
        json={
            "short_code": "VQ402EXP",
            "name": "VQ-402 Export Tenant",
            "storage_quota_mb": 100,
            "retention_days": 365,
        },
        headers=admin,
    )
    assert resp.status_code == 201, resp.text
    tenant_id = resp.json()["id"]

    # 2. create_invite
    resp = await async_client.post(
        f"/admin/tenants/{tenant_id}/invite",
        json={"email": "boss@vq402exp.com", "expires_in_hours": 168},
        headers=admin,
    )
    assert resp.status_code == 201, resp.text
    invite_code = resp.json()["code"]

    # 3. accept_invite
    resp = await async_client.post(
        "/invite/accept",
        json={"code": invite_code, "password": "StrongPass1!"},
    )
    assert resp.status_code == 200, resp.text

    login_body = {
        "organisation_code": "VQ402EXP",
        "email": "boss@vq402exp.com",
        "password": "StrongPass1!",
    }

    # 4. login
    resp = await async_client.post("/auth/login", json=login_body)
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    # 5. failed_login (wrong password)
    resp = await async_client.post(
        "/auth/login", json={**login_body, "password": "WrongPass1!"}
    )
    assert resp.status_code == 401

    # 6. upload_document
    resp = await async_client.post(
        "/documents",
        files={"file": ("export.txt", io.BytesIO(b"export payload"), "text/plain")},
        headers=auth,
    )
    assert resp.status_code == 201, resp.text
    doc_id = resp.json()["id"]

    # 7. delete_document
    resp = await async_client.delete(f"/documents/{doc_id}", headers=auth)
    assert resp.status_code == 204

    # 8. logout
    resp = await async_client.post("/auth/logout", headers=auth)
    assert resp.status_code == 200

    # 9. suspend_tenant (super admin action, recorded under the tenant)
    resp = await async_client.patch(
        f"/admin/tenants/{tenant_id}/suspend", headers=admin
    )
    assert resp.status_code == 200, resp.text

    # 10. reactivate_tenant
    resp = await async_client.patch(
        f"/admin/tenants/{tenant_id}/reactivate", headers=admin
    )
    assert resp.status_code == 200, resp.text

    # 11. login again (suspend revoked every session)
    resp = await async_client.post("/auth/login", json=login_body)
    assert resp.status_code == 200, resp.text
    token2 = resp.json()["access_token"]

    # 12. export — must contain all of the above
    resp = await async_client.get(
        "/audit/export?format=json",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    actions = _audit_actions(rows)

    expected = {
        "create_tenant",        # 1
        "create_invite",        # 2
        "accept_invite",        # 3
        "login",                # 4 (and 11)
        "failed_login",         # 5
        "upload_document",      # 6
        "delete_document",      # 7
        "logout",               # 8
        "suspend_tenant",       # 9
        "reactivate_tenant",    # 10
    }
    missing = expected - actions
    assert not missing, (
        f"Export is missing {sorted(missing)}; contains {sorted(actions)}"
    )
    assert "export_audit" in actions, "Export must record itself"
    assert len(rows) >= 11, f"Expected >= 11 rows, got {len(rows)}"


# ---------------------------------------------------------------------------
# 6. Retention policy plumbing
# ---------------------------------------------------------------------------

class TestRetentionPolicy:
    @pytest.mark.asyncio
    async def test_retention_days_defaults_and_customises(
        self, async_client, super_admin_token
    ):
        admin = {"Authorization": f"Bearer {super_admin_token}"}

        resp = await async_client.post(
            "/admin/tenants",
            json={"short_code": "RETDEF", "name": "Default Retention"},
            headers=admin,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["retention_days"] == 365

        resp = await async_client.post(
            "/admin/tenants",
            json={
                "short_code": "RETCUS",
                "name": "Custom Retention",
                "retention_days": 30,
            },
            headers=admin,
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["retention_days"] == 30

        # Recorded on the create_tenant audit row
        resp = await async_client.get(
            f"/admin/tenants/{resp.json()['id']}/audit", headers=admin
        )
        assert resp.status_code == 200
        create_rows = [r for r in resp.json() if r["action"] == "create_tenant"]
        assert create_rows
        assert create_rows[0]["details"]["retention_days"] == 30

    @pytest.mark.asyncio
    async def test_retention_days_rejects_zero(self, async_client, super_admin_token):
        resp = await async_client.post(
            "/admin/tenants",
            json={"short_code": "RETZERO", "name": "Bad Retention", "retention_days": 0},
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 422
