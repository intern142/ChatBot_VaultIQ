"""VQ-403: Tenant offboarding and full purge.

Covers: step-up identity re-confirmation, immediate lock + session revocation,
7-day cancellable grace, total purge (records + files), deletion report stored
outside the tenant, and role guards on all new endpoints.

IMPORTANT fixture rule: super_admin_token is always listed before tenant
fixtures — its db_conn/db_engine truncation must run before tenant data seeds.
"""
import json
import uuid

import pytest
from sqlalchemy import text

from app.offboard_purge import purge_due_tenants
from app.services.storage import get_tenant_storage_path

SUPER_PW = "AdminPass1!"       # super_admin_token fixture password
TENANT_PW = "StrongPass1!"     # tenant user fixture password


async def _offboard(async_client, super_admin_token, tenant_id, password=SUPER_PW):
    return await async_client.patch(
        f"/admin/tenants/{tenant_id}/offboard",
        json={"password": password},
        headers={"Authorization": f"Bearer {super_admin_token}"},
    )


async def _count(db_engine, sql, **params):
    async with db_engine.connect() as conn:
        result = await conn.execute(text(sql), params)
        return result.scalar()


# ---------------------------------------------------------------------------
# 1. Offboard: identity re-confirmation, lock, sessions, audit
# ---------------------------------------------------------------------------


class TestOffboard:
    async def test_offboard_happy_path(
        self, async_client, super_admin_token, tenant_a, db_engine
    ):
        tid = tenant_a["id"]
        resp = await _offboard(async_client, super_admin_token, tid)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "offboarding"
        assert body["offboarded_at"] is not None
        assert body["purge_after"] is not None
        assert body["purged_at"] is None

        # grace window is 7 days (assert 6.9–7.1 days out to dodge clock skew)
        from datetime import datetime, timezone

        purge_after = datetime.fromisoformat(body["purge_after"])
        delta_days = (purge_after - datetime.now(timezone.utc)).total_seconds() / 86400
        assert 6.9 <= delta_days <= 7.1

        # all sessions revoked
        n = await _count(
            db_engine, "SELECT count(*) FROM sessions WHERE tenant_id = :t", t=tid
        )
        assert n == 0

        # lock: login refused immediately
        resp = await async_client.post(
            "/auth/login",
            json={
                "organisation_code": "TENANT_A",
                "email": "admin@a.com",
                "password": TENANT_PW,
            },
        )
        assert resp.status_code == 403

        # audit recorded
        n = await _count(
            db_engine,
            "SELECT count(*) FROM audit_logs WHERE tenant_id = :t AND action = 'offboard_tenant'",
            t=tid,
        )
        assert n == 1

    async def test_offboard_wrong_password_rejected(
        self, async_client, super_admin_token, tenant_a, db_engine
    ):
        tid = tenant_a["id"]
        resp = await _offboard(
            async_client, super_admin_token, tid, password="WrongPass1!"
        )
        assert resp.status_code == 403
        assert "re-confirmation" in resp.json()["detail"]

        # no state change
        n = await _count(
            db_engine, "SELECT count(*) FROM tenants WHERE id = :t AND status = 'active'", t=tid
        )
        assert n == 1
        n = await _count(
            db_engine, "SELECT count(*) FROM sessions WHERE tenant_id = :t", t=tid
        )
        assert n == 2
        n = await _count(
            db_engine,
            "SELECT count(*) FROM audit_logs WHERE tenant_id = :t AND action = 'offboard_tenant'",
            t=tid,
        )
        assert n == 0

    async def test_offboard_twice_conflict(
        self, async_client, super_admin_token, tenant_a
    ):
        tid = tenant_a["id"]
        resp = await _offboard(async_client, super_admin_token, tid)
        assert resp.status_code == 200
        resp = await _offboard(async_client, super_admin_token, tid)
        assert resp.status_code == 409

    async def test_offboard_purged_tenant_conflict(
        self, async_client, super_admin_token, tenant_a, db_engine
    ):
        tid = tenant_a["id"]
        async with db_engine.begin() as conn:
            await conn.execute(
                text("UPDATE tenants SET status = 'purged' WHERE id = :t"), {"t": tid}
            )
        resp = await _offboard(async_client, super_admin_token, tid)
        assert resp.status_code == 409

    async def test_offboard_unknown_tenant_404(
        self, async_client, super_admin_token
    ):
        resp = await _offboard(async_client, super_admin_token, uuid.uuid4())
        assert resp.status_code == 404

    async def test_offboard_from_suspended_allowed(
        self, async_client, super_admin_token, tenant_a
    ):
        tid = tenant_a["id"]
        resp = await async_client.patch(
            f"/admin/tenants/{tid}/suspend",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200, resp.text
        resp = await _offboard(async_client, super_admin_token, tid)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "offboarding"


# ---------------------------------------------------------------------------
# 2. Grace period: cancellation
# ---------------------------------------------------------------------------


class TestCancelOffboarding:
    async def test_cancel_restores_tenant(
        self, async_client, super_admin_token, tenant_a, db_engine
    ):
        tid = tenant_a["id"]
        resp = await _offboard(async_client, super_admin_token, tid)
        assert resp.status_code == 200

        resp = await async_client.patch(
            f"/admin/tenants/{tid}/cancel-offboarding",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "active"
        assert body["offboarded_at"] is None
        assert body["purge_after"] is None

        # login works again (sessions were revoked at offboard, new one issued)
        resp = await async_client.post(
            "/auth/login",
            json={
                "organisation_code": "TENANT_A",
                "email": "admin@a.com",
                "password": TENANT_PW,
            },
        )
        assert resp.status_code == 200, resp.text

        n = await _count(
            db_engine,
            "SELECT count(*) FROM audit_logs WHERE tenant_id = :t AND action = 'cancel_offboarding'",
            t=tid,
        )
        assert n == 1

    async def test_cancel_active_tenant_conflict(
        self, async_client, super_admin_token, tenant_a
    ):
        resp = await async_client.patch(
            f"/admin/tenants/{tenant_a['id']}/cancel-offboarding",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 409

    async def test_cancel_purged_tenant_conflict(
        self, async_client, super_admin_token, tenant_a, db_engine
    ):
        async with db_engine.begin() as conn:
            await conn.execute(
                text("UPDATE tenants SET status = 'purged' WHERE id = :t"),
                {"t": tenant_a["id"]},
            )
        resp = await async_client.patch(
            f"/admin/tenants/{tenant_a['id']}/cancel-offboarding",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 409

    async def test_cancel_unknown_tenant_404(
        self, async_client, super_admin_token
    ):
        resp = await async_client.patch(
            f"/admin/tenants/{uuid.uuid4()}/cancel-offboarding",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 3. Role guards — non-super-admins denied on all four endpoints
# ---------------------------------------------------------------------------


class TestRoleGuards:
    async def test_client_admin_denied_everywhere(
        self, async_client, token_a_admin, tenant_a
    ):
        headers = {"Authorization": f"Bearer {token_a_admin}"}
        tid = str(tenant_a["id"])

        resp = await async_client.patch(
            f"/admin/tenants/{tid}/offboard", json={"password": TENANT_PW}, headers=headers
        )
        assert resp.status_code == 403

        resp = await async_client.patch(
            f"/admin/tenants/{tid}/cancel-offboarding", headers=headers
        )
        assert resp.status_code == 403

        resp = await async_client.get("/admin/deletion-reports", headers=headers)
        assert resp.status_code == 403

        resp = await async_client.get(
            f"/admin/deletion-reports/{uuid.uuid4()}", headers=headers
        )
        assert resp.status_code == 403

    async def test_employee_denied_everywhere(
        self, async_client, token_a_emp, tenant_a
    ):
        headers = {"Authorization": f"Bearer {token_a_emp}"}
        tid = str(tenant_a["id"])

        resp = await async_client.patch(
            f"/admin/tenants/{tid}/offboard", json={"password": TENANT_PW}, headers=headers
        )
        assert resp.status_code == 403

        resp = await async_client.patch(
            f"/admin/tenants/{tid}/cancel-offboarding", headers=headers
        )
        assert resp.status_code == 403

        resp = await async_client.get("/admin/deletion-reports", headers=headers)
        assert resp.status_code == 403

    async def test_unauthenticated_denied(self, async_client, tenant_a):
        resp = await async_client.patch(
            f"/admin/tenants/{tenant_a['id']}/offboard", json={"password": SUPER_PW}
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 4. Purge: grace enforcement, total removal, other tenants untouched
# ---------------------------------------------------------------------------


class TestPurge:
    async def test_purge_before_grace_is_noop(self, tenant_a, db_engine):
        """Offboarding but not yet due: the job must not touch it."""
        tid = tenant_a["id"]
        async with db_engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    UPDATE tenants
                    SET status = 'offboarding', offboarded_at = now(),
                        purge_after = now() + interval '3 days'
                    WHERE id = :t
                    """
                ),
                {"t": tid},
            )

        purged = await purge_due_tenants()
        assert purged == []

        n = await _count(
            db_engine, "SELECT count(*) FROM users WHERE tenant_id = :t", t=tid
        )
        assert n == 2
        n = await _count(
            db_engine,
            "SELECT status FROM tenants WHERE id = :t",
            t=tid,
        )
        assert n == "offboarding"

    async def test_function_refuses_early_purge(self, tenant_a, db_engine):
        """The grace check lives inside the SQL function, not app code."""
        tid = tenant_a["id"]
        async with db_engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    UPDATE tenants
                    SET status = 'offboarding', offboarded_at = now(),
                        purge_after = now() + interval '3 days'
                    WHERE id = :t
                    """
                ),
                {"t": tid},
            )

        with pytest.raises(Exception) as exc_info:
            async with db_engine.connect() as conn:
                await conn.execute(text("SELECT purge_tenant(:t)"), {"t": tid})
        assert "not eligible" in str(exc_info.value)

    async def test_must_prove_total_purge_and_other_tenant_untouched(
        self,
        async_client,
        super_admin_token,
        doc_a,
        tenant_b,
        token_b_admin,
        db_engine,
    ):
        """AC must-prove: after purge, zero records + zero files for tenant A;
        tenant B (rows + files) byte-identical before/after; deletion report
        exists outside the tenant with counts matching reality."""
        tid_a = doc_a["tenant_id"]
        tid_b = tenant_b["id"]

        # seed: an invite for tenant A (SQL — A already has a client admin)
        async with db_engine.begin() as conn:
            await conn.execute(
                text(
                    """
                    INSERT INTO invites (tenant_id, email, code, expires_at, created_by)
                    SELECT :t, 'leaving@a.com', :c, now() + interval '1 day', id
                    FROM users WHERE tenant_id = :t AND role = 'client_admin'
                    """
                ),
                {"t": tid_a, "c": uuid.uuid4().hex[:40]},
            )

        # a file that must survive: tenant B storage
        b_dir = get_tenant_storage_path(tid_b)
        b_dir.mkdir(parents=True, exist_ok=True)
        b_file = b_dir / "keep.txt"
        b_file.write_bytes(b"tenant-b-must-survive")

        # baseline counts (tenant B)
        baseline = {}
        for table in ["users", "sessions", "invites", "audit_logs", "documents"]:
            baseline[table] = await _count(
                db_engine,
                f"SELECT count(*) FROM {table} WHERE tenant_id = :t",
                t=tid_b,
            )
        baseline["sessions"] = 2
        assert baseline["users"] == 2

        a_dir = get_tenant_storage_path(tid_a)
        assert a_dir.exists(), "uploaded document storage should exist"

        # offboard A (legitimately, through the API)
        resp = await _offboard(async_client, super_admin_token, tid_a)
        assert resp.status_code == 200, resp.text

        # sessions already gone at offboard time
        n = await _count(
            db_engine, "SELECT count(*) FROM sessions WHERE tenant_id = :t", t=tid_a
        )
        assert n == 0

        # backdate grace so the job considers A due
        async with db_engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE tenants SET purge_after = now() - interval '1 day' WHERE id = :t"
                ),
                {"t": tid_a},
            )

        purged = await purge_due_tenants()
        assert len(purged) == 1
        assert purged[0]["short_code"] == "TENANT_A"

        # --- zero tenant-scoped records for A ---
        for table in ["users", "sessions", "invites", "audit_logs", "documents"]:
            n = await _count(
                db_engine,
                f"SELECT count(*) FROM {table} WHERE tenant_id = :t",
                t=tid_a,
            )
            assert n == 0, f"tenant A still has {n} rows in {table}"

        # --- zero files for A ---
        assert not a_dir.exists(), "tenant A storage directory still exists"

        # --- tombstone ---
        row = None
        async with db_engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT status, purged_at FROM tenants WHERE id = :t"
                    ),
                    {"t": tid_a},
                )
            ).one()
        assert row[0] == "purged"
        assert row[1] is not None

        # --- tenant B untouched: same rows, same files ---
        for table in ["users", "sessions", "invites", "audit_logs", "documents"]:
            n = await _count(
                db_engine,
                f"SELECT count(*) FROM {table} WHERE tenant_id = :t",
                t=tid_b,
            )
            assert n == baseline[table], f"tenant B {table}: {baseline[table]} -> {n}"
        assert b_file.exists()
        assert b_file.read_bytes() == b"tenant-b-must-survive"

        # --- deletion report: stored outside the tenant, counts match reality ---
        async with db_engine.connect() as conn:
            rep = (
                await conn.execute(
                    text(
                        """
                        SELECT report, backup_flag, grace_days, initiated_by, initiated_at
                        FROM deletion_reports WHERE tenant_id = :t
                        """
                    ),
                    {"t": tid_a},
                )
            ).one()
        assert rep is not None
        report = rep[0] if isinstance(rep[0], dict) else json.loads(rep[0])
        flag = rep[1] if isinstance(rep[1], dict) else json.loads(rep[1])
        assert report["rows_deleted"]["users"] == 2
        assert report["rows_deleted"]["invites"] == 1
        assert report["rows_deleted"]["documents"] == 1
        assert report["rows_deleted"]["sessions"] == 0  # revoked at offboard
        assert report["rows_deleted"]["audit_logs"] >= 1
        assert report["files_deleted"] >= 1
        assert report["bytes_deleted"] > 0
        assert flag["state"] == "eligible_for_expiry"
        assert "flagged_at" in flag
        assert rep[2] == 7
        assert rep[3] is not None  # initiated_by = the super admin who offboarded
        assert rep[4] is not None  # initiated_at = offboarded_at

        # --- report readable by super_admin via API, invisible to client admin ---
        resp = await async_client.get(
            "/admin/deletion-reports",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200, resp.text
        reports = resp.json()
        match = [r for r in reports if r["tenant_id"] == tid_a]
        assert len(match) == 1
        report_id = match[0]["id"]

        resp = await async_client.get(
            f"/admin/deletion-reports/{report_id}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["short_code"] == "TENANT_A"

        # tenant B's admin (still active tenant) must not see platform reports
        resp = await async_client.get(
            "/admin/deletion-reports",
            headers={"Authorization": f"Bearer {token_b_admin}"},
        )
        assert resp.status_code == 403

        # --- second run: nothing left to purge (idempotent) ---
        purged_again = await purge_due_tenants()
        assert purged_again == []

    async def test_report_404_unknown_id(self, async_client, super_admin_token):
        resp = await async_client.get(
            f"/admin/deletion-reports/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 404

    async def test_guarded_derived_tables_purged_skipped_when_unsafe(
        self, tenant_a, db_engine
    ):
        """AC3 derived artefacts: listed tables WITH tenant_id are purged and
        counted; listed tables WITHOUT tenant_id are skipped without error
        (future-proofing against derived tables that aren't tenant-scoped)."""
        tid = tenant_a["id"]
        async with db_engine.begin() as conn:
            # exists + has tenant_id -> must be purged
            await conn.execute(text(
                """
                CREATE TABLE text_chunks (
                    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id uuid REFERENCES tenants(id),
                    content text
                )
                """
            ))
            await conn.execute(
                text(
                    "INSERT INTO text_chunks (tenant_id, content) VALUES (:t, 'secret')"
                ),
                {"t": tid},
            )
            # exists, listed, but NO tenant_id -> must be skipped, not error
            await conn.execute(text(
                """
                CREATE TABLE cached_answers (
                    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                    answer text
                )
                """
            ))
            await conn.execute(text(
                "INSERT INTO cached_answers (answer) VALUES ('keep me')"
            ))
            await conn.execute(
                text(
                    """
                    UPDATE tenants
                    SET status = 'offboarding', offboarded_at = now() - interval '8 days',
                        purge_after = now() - interval '1 day'
                    WHERE id = :t
                    """
                ),
                {"t": tid},
            )

        try:
            purged = await purge_due_tenants()
            assert len(purged) == 1

            async with db_engine.connect() as conn:
                n = (
                    await conn.execute(
                        text(
                            "SELECT count(*) FROM text_chunks WHERE tenant_id = :t"
                        ),
                        {"t": tid},
                    )
                ).scalar()
                assert n == 0, "derived table with tenant_id was not purged"

                n = (
                    await conn.execute(text(
                        "SELECT count(*) FROM cached_answers"
                    ))
                ).scalar()
                assert n == 1, "table without tenant_id must be skipped untouched"

                rep = (
                    await conn.execute(
                        text(
                            "SELECT report FROM deletion_reports WHERE tenant_id = :t"
                        ),
                        {"t": tid},
                    )
                ).scalar()
            report = rep if isinstance(rep, dict) else json.loads(rep)
            assert report["rows_deleted"]["text_chunks"] == 1
            assert "cached_answers" not in report["rows_deleted"]
        finally:
            async with db_engine.begin() as conn:
                await conn.execute(text("DROP TABLE IF EXISTS text_chunks"))
                await conn.execute(text("DROP TABLE IF EXISTS cached_answers"))
