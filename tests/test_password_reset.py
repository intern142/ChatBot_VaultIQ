"""VQ-301 AC4: Client Admin issues a one-time password-reset code, the user
consumes it.

The properties under test, in the order they matter:

  * a code is one-time and expires
  * the reset actually changes the credential (old fails, new works)
  * a reset ends the account's existing sessions and clears any lockout
  * every way of failing looks identical to the caller
  * one tenant's code cannot touch another tenant
  * the code is not recoverable from the database

Actor note: the issuer is a Client Admin acting inside their own tenant. An
earlier draft of this story had the Super Admin issue the code; that was wrong
(see APPROACH_VQ301.md) and none of it survives.
"""
import asyncio
import hashlib
import time

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from app.auth.password import hash_password, verify_password
from app.models.audit_log import AuditLog
from app.models.reset_code import ResetCode
from app.models.session import Session
from app.models.user import User
from app.routes.auth import RESET_FAILURE_DETAIL, RESET_MIN_ELAPSED


ISSUE = "/users/{user_id}/password-reset"
CONSUME = "/auth/reset-password"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _issue(client, token, user_id):
    return await client.post(ISSUE.format(user_id=user_id), headers=_headers(token))


async def _consume(client, code, new_password="NewStrong1!"):
    return await client.post(
        CONSUME, json={"code": code, "new_password": new_password}
    )


async def _stored_code_hash(db_engine, code: str) -> str:
    """Read the persisted digest as the superuser, bypassing RLS.

    The application can only ever see rows through the policies; this is the
    test asserting what actually landed on disk.
    """
    async with db_engine.begin() as conn:
        result = await conn.execute(
            text("SELECT code_hash FROM reset_codes WHERE code_hash = :h"),
            {"h": hashlib.sha256(code.encode()).hexdigest()},
        )
        return result.scalar_one_or_none()


class TestIssueCode:
    """POST /users/{user_id}/password-reset"""

    async def test_client_admin_issues_code_for_own_employee(
        self, async_client, tenant_a, token_a_admin
    ):
        resp = await _issue(async_client, token_a_admin, tenant_a["employee"]["id"])
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert len(body["reset_code"]) == 43
        assert body["expires_at"]

    async def test_employee_cannot_issue_code(
        self, async_client, tenant_a, token_a_emp
    ):
        resp = await _issue(async_client, token_a_emp, tenant_a["employee"]["id"])
        assert resp.status_code == 403

    async def test_super_admin_cannot_issue_code(
        self, async_client, tenant_a, super_admin_token
    ):
        """VQ-106 AC4 keeps platform operators out of tenant user management."""
        resp = await _issue(
            async_client, super_admin_token, tenant_a["employee"]["id"]
        )
        assert resp.status_code == 403

    async def test_cannot_target_another_tenant(
        self, async_client, tenant_a, tenant_b, token_a_admin, db_engine
    ):
        resp = await _issue(
            async_client, token_a_admin, tenant_b["employee"]["id"]
        )
        # 404, not 403: another tenant's user must not be confirmed to exist.
        assert resp.status_code == 404
        async with db_engine.begin() as conn:
            count = await conn.execute(text("SELECT count(*) FROM reset_codes"))
            assert count.scalar_one() == 0

    async def test_cannot_reset_own_account(
        self, async_client, tenant_a, token_a_admin
    ):
        resp = await _issue(
            async_client, token_a_admin, tenant_a["client_admin"]["id"]
        )
        assert resp.status_code == 400

    async def test_code_is_not_stored_in_plaintext(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        resp = await _issue(async_client, token_a_admin, tenant_a["employee"]["id"])
        code = resp.json()["reset_code"]

        stored = await _stored_code_hash(db_engine, code)
        assert stored is not None, "code was not persisted at all"
        assert stored != code, "code was stored in plaintext"
        assert len(stored) == 64, "expected a sha256 hex digest"
        assert stored == hashlib.sha256(code.encode()).hexdigest()

    async def test_fourth_live_code_revokes_the_oldest(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        issued = []
        for _ in range(4):
            resp = await _issue(
                async_client, token_a_admin, tenant_a["employee"]["id"]
            )
            assert resp.status_code == 201
            issued.append(resp.json()["reset_code"])

        # The first was revoked to make room, so it no longer consumes.
        assert (await _consume(async_client, issued[0])).status_code == 401
        # The newest is still good.
        assert (await _consume(async_client, issued[-1])).status_code == 200


class TestConsumeCode:
    """POST /auth/reset-password"""

    async def test_valid_code_changes_the_password(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        target = tenant_a["employee"]["id"]
        code = (await _issue(async_client, token_a_admin, target)).json()["reset_code"]

        assert (await _consume(async_client, code)).status_code == 200

        async with db_engine.begin() as conn:
            result = await conn.execute(
                text("SELECT password_hash FROM users WHERE id = :id"), {"id": target}
            )
            assert verify_password("NewStrong1!", result.scalar_one())

    async def test_old_password_stops_working_and_new_one_works(
        self, async_client, tenant_a, token_a_admin
    ):
        code = (
            await _issue(
                async_client, token_a_admin, tenant_a["employee"]["id"]
            )
        ).json()["reset_code"]
        assert (await _consume(async_client, code)).status_code == 200

        # tenant_a fixture seeds employee with this password.
        old = await async_client.post(
            "/auth/login",
            json={
                "organisation_code": "TENANT_A",
                "email": "emp@a.com",
                "password": "StrongPass1!",
            },
        )
        assert old.status_code == 401

        new = await async_client.post(
            "/auth/login",
            json={
                "organisation_code": "TENANT_A",
                "email": "emp@a.com",
                "password": "NewStrong1!",
            },
        )
        assert new.status_code == 200

    async def test_weak_password_rejected_and_code_survives(
        self, async_client, tenant_a, token_a_admin
    ):
        code = (
            await _issue(
                async_client, token_a_admin, tenant_a["employee"]["id"]
            )
        ).json()["reset_code"]

        weak = await _consume(async_client, code, new_password="weak")
        assert weak.status_code == 400

        # Not consumed by the rejected attempt.
        assert (await _consume(async_client, code)).status_code == 200

    async def test_code_is_single_use(
        self, async_client, tenant_a, token_a_admin
    ):
        code = (
            await _issue(
                async_client, token_a_admin, tenant_a["employee"]["id"]
            )
        ).json()["reset_code"]

        assert (await _consume(async_client, code)).status_code == 200
        second = await _consume(async_client, code, new_password="OtherStrong1!")
        assert second.status_code == 401
        assert second.json()["detail"] == RESET_FAILURE_DETAIL

    async def test_expired_code_rejected(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        code = (
            await _issue(
                async_client, token_a_admin, tenant_a["employee"]["id"]
            )
        ).json()["reset_code"]

        async with db_engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE reset_codes SET expires_at = now() - interval '1 hour' "
                    "WHERE code_hash = :h"
                ),
                {"h": hashlib.sha256(code.encode()).hexdigest()},
            )

        resp = await _consume(async_client, code)
        assert resp.status_code == 401
        assert resp.json()["detail"] == RESET_FAILURE_DETAIL

    async def test_concurrent_claims_yield_exactly_one_success(
        self, async_client, tenant_a, token_a_admin
    ):
        code = (
            await _issue(
                async_client, token_a_admin, tenant_a["employee"]["id"]
            )
        ).json()["reset_code"]

        results = await asyncio.gather(
            _consume(async_client, code, new_password="RaceStrong1!"),
            _consume(async_client, code, new_password="RaceStrong1!"),
            _consume(async_client, code, new_password="RaceStrong1!"),
        )
        codes = sorted(r.status_code for r in results)
        assert codes == [200, 401, 401], codes

    async def test_unknown_and_malformed_codes_are_indistinguishable(
        self, async_client
    ):
        """Every unusable code must produce the same answer.

        An empty string is excluded: the schema rejects it with 422 before any
        code is consulted, which is a different thing entirely and cannot be
        used to probe whether a code exists.
        """
        responses = []
        for bad in (
            "not-a-real-code",
            "x" * 43,
            "a/b+c=",
            "0" * 64,
        ):
            resp = await async_client.post(
                CONSUME, json={"code": bad, "new_password": "NewStrong1!"}
            )
            responses.append(resp)

        statuses = {r.status_code for r in responses}
        bodies = {r.json()["detail"] for r in responses}
        assert statuses == {401}, statuses
        assert bodies == {RESET_FAILURE_DETAIL}, bodies

    async def test_failures_take_at_least_the_floor_time(
        self, async_client, tenant_a, token_a_admin
    ):
        """AC: the failure paths must not be distinguishable by how fast they answer.

        The endpoint sleeps out the remainder of a 200ms floor before rejecting,
        so an unknown code and a spent code take comparable time rather than
        letting a caller time its way to a list of live codes.
        """
        code = (
            await _issue(
                async_client, token_a_admin, tenant_a["employee"]["id"]
            )
        ).json()["reset_code"]
        assert (await _consume(async_client, code)).status_code == 200

        async def timed(payload: dict) -> float:
            started = time.perf_counter()
            resp = await async_client.post(CONSUME, json=payload)
            elapsed = time.perf_counter() - started
            assert resp.status_code == 401
            return elapsed

        used = await timed({"code": code, "new_password": "NewStrong1!"})
        unknown = await timed({"code": "unknown-code", "new_password": "NewStrong1!"})
        expired_shape = await timed({"code": "x" * 43, "new_password": "NewStrong1!"})

        floor = RESET_MIN_ELAPSED.total_seconds()
        for label, elapsed in (
            ("used", used),
            ("unknown", unknown),
            ("malformed", expired_shape),
        ):
            assert elapsed >= floor, f"{label} answered in {elapsed:.3f}s, under the floor"

        spread = max(used, unknown, expired_shape) - min(
            used, unknown, expired_shape
        )
        assert spread < floor, f"failure timings diverged by {spread:.3f}s"

    async def test_empty_code_is_a_schema_error(self, async_client):
        resp = await async_client.post(
            CONSUME, json={"code": "", "new_password": "NewStrong1!"}
        )
        assert resp.status_code == 422

    async def test_cross_tenant_code_cannot_be_used(
        self, async_client, tenant_a, tenant_b, token_a_admin, db_engine
    ):
        """Tenant A's code must not reach tenant B.

        The code is a bearer credential, so this is the case worth being afraid
        of. What must be impossible is the claim writing anywhere except the
        tenant recorded on the row it unlocked, and any other tenant being
        observable through the response.
        """
        code = (
            await _issue(
                async_client, token_a_admin, tenant_a["employee"]["id"]
            )
        ).json()["reset_code"]

        resp = await _consume(async_client, code)
        assert resp.status_code == 200

        # B's user is untouched, and no code row exists for B at all.
        async with db_engine.begin() as conn:
            result = await conn.execute(
                text("SELECT password_hash FROM users WHERE id = :id"),
                {"id": tenant_b["employee"]["id"]},
            )
            assert verify_password("StrongPass1!", result.scalar_one())

            result = await conn.execute(
                text("SELECT count(*) FROM reset_codes WHERE tenant_id = :t"),
                {"t": tenant_b["id"]},
            )
            assert result.scalar_one() == 0

            # B's sessions were not disturbed by A's reset.
            live = await conn.execute(
                text(
                    "SELECT count(*) FROM sessions "
                    "WHERE user_id = :u AND is_revoked = false"
                ),
                {"u": tenant_b["employee"]["id"]},
            )
            assert live.scalar_one() >= 1


class TestSessionAndLockout:
    async def test_reset_revokes_existing_sessions(
        self, async_client, tenant_a, token_a_admin, token_a_emp
    ):
        # token_a_emp's session row exists from the tenant_a fixture.
        before = await async_client.post(
            "/auth/refresh", headers=_headers(token_a_emp)
        )
        assert before.status_code == 200

        code = (
            await _issue(
                async_client, token_a_admin, tenant_a["employee"]["id"]
            )
        ).json()["reset_code"]
        assert (await _consume(async_client, code)).status_code == 200

        after = await async_client.post(
            "/auth/refresh", headers=_headers(token_a_emp)
        )
        assert after.status_code == 401, "session survived a password reset"

    async def test_reset_clears_a_lockout(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        target = tenant_a["employee"]["id"]
        async with db_engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE users SET failed_login_attempts = 5, "
                    "locked_until = now() + interval '15 minutes' WHERE id = :id"
                ),
                {"id": target},
            )

        code = (
            await _issue(async_client, token_a_admin, target)
        ).json()["reset_code"]
        assert (await _consume(async_client, code)).status_code == 200

        login = await async_client.post(
            "/auth/login",
            json={
                "organisation_code": "TENANT_A",
                "email": "emp@a.com",
                "password": "NewStrong1!",
            },
        )
        assert login.status_code == 200, "lockout survived the reset"


class TestAudit:
    async def test_both_actions_are_audited(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        target = tenant_a["employee"]["id"]
        code = (
            await _issue(async_client, token_a_admin, target)
        ).json()["reset_code"]
        assert (await _consume(async_client, code)).status_code == 200

        async with db_engine.begin() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT action, actor_user_id, actor_role, target_id "
                        "FROM audit_logs WHERE target_id = :t "
                        "ORDER BY created_at"
                    ),
                    {"t": target},
                )
            ).all()

        actions = [r[0] for r in rows]
        assert "request_password_reset" in actions
        assert "complete_password_reset" in actions

        request_row = next(r for r in rows if r[0] == "request_password_reset")
        # Issuer is the Client Admin who asked for it.
        assert request_row[1] == tenant_a["client_admin"]["id"]
        assert request_row[2] == "client_admin"

        complete_row = next(r for r in rows if r[0] == "complete_password_reset")
        # Completer is the user whose password changed.
        assert complete_row[1] == target
        assert complete_row[2] == "employee"

    async def test_code_value_is_not_audited(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        code = (
            await _issue(
                async_client, token_a_admin, tenant_a["employee"]["id"]
            )
        ).json()["reset_code"]

        async with db_engine.begin() as conn:
            rows = (await conn.execute(text("SELECT details::text FROM audit_logs"))).all()
            blob = " ".join(str(r[0]) for r in rows)

        assert code not in blob, "reset code leaked into the audit trail"


class TestRowLevelSecurity:
    """The policies themselves, exercised as `vaultiq_app` (NOBYPASSRLS).

    These do not go through HTTP. The application connection used elsewhere in
    this file is whatever `APP_DATABASE_URL` points at, which locally is the
    superuser, so an HTTP-only test would silently pass with every policy
    inert. Talking to the database as the app role is the only way to show the
    refusal is coming from Postgres.
    """

    @pytest.fixture
    def seeded(self, db_conn, db_engine):
        """Two tenants, one user each, one live reset code in tenant A."""
        # Ensure clean state (db_engine fixture truncates, but only if it runs)
        cur = db_conn.cursor()
        cur.execute("TRUNCATE users, tenants, sessions, documents, invites, audit_logs, reset_codes CASCADE")
        db_conn.commit()
        
        cur.execute(
            "INSERT INTO tenants (short_code, name) VALUES ('RA', 'Rls A') "
            "RETURNING id"
        )
        tenant_a = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO tenants (short_code, name) VALUES ('RB', 'Rls B') "
            "RETURNING id"
        )
        tenant_b = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO users (tenant_id, email, password_hash, role) "
            "VALUES (%s, 'a@ra.com', 'x', 'employee') RETURNING id",
            (str(tenant_a),),
        )
        user_a = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO users (tenant_id, email, password_hash, role) "
            "VALUES (%s, 'b@rb.com', 'x', 'employee') RETURNING id",
            (str(tenant_b),),
        )
        user_b = cur.fetchone()[0]

        code_hash = hashlib.sha256(b"rls-test-code").hexdigest()
        cur.execute(
            "INSERT INTO reset_codes "
            "(tenant_id, user_id, code_hash, expires_at) "
            "VALUES (%s, %s, %s, now() + interval '1 hour')",
            (str(tenant_a), str(user_a), code_hash),
        )
        db_conn.commit()
        return {
            "conn": db_conn,
            "tenant_a": tenant_a,
            "tenant_b": tenant_b,
            "user_a": user_a,
            "user_b": user_b,
            "code_hash": code_hash,
        }

    def _count(self, conn, sql, params=None):
        cur = conn.cursor()
        cur.execute(sql, params or {})
        return cur.fetchone()[0]

    def test_no_context_session_sees_nothing(self, seeded, app_db_conn):
        count = self._count(app_db_conn, "SELECT count(*) FROM reset_codes")
        assert count == 0, "a no-tenant session must not see reset codes"

    def test_code_hash_lookup_sees_exactly_that_row(self, seeded, app_db_conn):
        app_db_conn.rollback()
        cur = app_db_conn.cursor()
        cur.execute(
            "SELECT set_config('app.reset_code_hash', %s, true)", (seeded["code_hash"],)
        )
        count = self._count(app_db_conn, "SELECT count(*) FROM reset_codes")
        assert count == 1

    def test_wrong_code_hash_sees_nothing(self, seeded, app_db_conn):
        cur = app_db_conn.cursor()
        cur.execute(
            "SELECT set_config('app.reset_code_hash', %s, true)", ("0" * 64,)
        )
        count = self._count(app_db_conn, "SELECT count(*) FROM reset_codes")
        assert count == 0

    def test_tenant_context_sees_only_own_tenant(self, seeded, app_db_conn):
        cur = app_db_conn.cursor()
        cur.execute(
            "SELECT set_config('app.current_tenant', %s, true)",
            (str(seeded["tenant_a"]),),
        )
        count = self._count(app_db_conn, "SELECT count(*) FROM reset_codes")
        assert count == 1

        cur.execute(
            "SELECT set_config('app.current_tenant', %s, true)",
            (str(seeded["tenant_b"]),),
        )
        count = self._count(app_db_conn, "SELECT count(*) FROM reset_codes")
        assert count == 0, "tenant B must not see tenant A's reset codes"

    def test_tenant_context_does_not_grant_a_public_claim(
        self, seeded, app_db_conn
    ):
        """The lookup policy must not be a back door to another tenant's row.

        Holding tenant B's context is not a substitute for holding a code: the
        tenant policy only ever matches B's own rows.
        """
        cur = app_db_conn.cursor()
        cur.execute(
            "SELECT set_config('app.current_tenant', %s, true)",
            (str(seeded["tenant_b"]),),
        )
        count = self._count(
            app_db_conn,
            "SELECT count(*) FROM reset_codes WHERE tenant_id = %s",
            (str(seeded["tenant_a"]),),
        )
        assert count == 0

    def test_no_context_session_cannot_write(self, seeded, app_db_conn):
        """A no-context session must not be able to consume a code.

        Note the assertion is on the row count, not on an exception. A missing
        GRANT would raise InsufficientPrivilegeError, but RLS filtering is not an
        error: the statement succeeds and matches nothing. Asserting that it
        "raises" would have passed for the wrong reason and proved nothing.
        """
        cur = app_db_conn.cursor()
        cur.execute(
            "UPDATE reset_codes SET used_at = now() WHERE code_hash = %s",
            (seeded["code_hash"],),
        )
        assert cur.rowcount == 0, "a no-context session consumed a reset code"
        app_db_conn.rollback()

        # And the row really is untouched, read back as the superuser.
        cur = seeded["conn"].cursor()
        cur.execute(
            "SELECT used_at FROM reset_codes WHERE code_hash = %s",
            (seeded["code_hash"],),
        )
        assert cur.fetchone()[0] is None
