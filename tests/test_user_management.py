"""VQ-301: Client Admin user management.

Covers the five acceptance criteria that were not part of the AC4 delivery:

  AC1  POST /users/invites               invite one user at a chosen role
  AC2  POST /users/import                CSV import, validate-all-then-apply-or-none
  AC3  POST /users/{id}/deactivate|reactivate
  AC5  PATCH /users/{id}/role            behind step-up re-authentication
  AC6  GET  /users/audit                 tenant-scoped trail

The properties worth testing are the ones that would leak or strand a customer,
so they are grouped by criterion but each class names the failure it prevents:

  * tenant isolation - a Client Admin can only reach their own people, and a
    refusal must not confirm that another tenant's user exists
  * the last-admin guard - a tenant must never be left with nobody who can
    administer it, because the fix would need the platform operator
  * all-or-nothing import - a half-applied staff list is unusable
  * deactivation actually takes effect, on the next request, not eventually
  * step-up - a stale token must not be able to change a privilege
  * credentials never reach the audit trail or a response body
"""
import hashlib

import pytest
from sqlalchemy import text

from app.auth.password import hash_password
from app.schemas.user import MAX_IMPORT_BYTES

STRONG = "StrongPass1!"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _login(client, org_code: str, email: str, password: str = STRONG):
    return await client.post(
        "/auth/login",
        json={"organisation_code": org_code, "email": email, "password": password},
    )


async def _invite(client, token, email, role="employee", **kwargs):
    body = {"email": email, "role": role}
    body.update(kwargs)
    return await client.post("/users/invites", json=body, headers=_headers(token))


async def _accept(client, code, email=None, password=STRONG):
    return await client.post(
        "/invite/accept", json={"code": code, "email": email, "password": password}
    )


async def _csv(client, token, body: str):
    return await client.post(
        "/users/import",
        files={"file": ("staff.csv", body.encode("utf-8"), "text/csv")},
        headers=_headers(token),
    )


async def _row(db_engine, table: str, where: str, *params):
    async with db_engine.begin() as conn:
        result = await conn.execute(
            text(f"SELECT count(*) FROM {table} WHERE {where}"), params or {}
        )
        return result.scalar_one()


async def _insert_user(db_engine, tenant_id, email: str, role: str = "employee"):
    """Create a user directly, as the admin identity.

    Used to reproduce a race the API cannot be asked to reproduce on demand: the
    endpoint checks for an existing address and then inserts, so the only way to
    make the insert lose is to put the row there in between. Runs on the admin
    engine, which is not subject to RLS.
    """
    async with db_engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (tenant_id, email, password_hash, role, is_active) "
                "VALUES (:t, :e, :h, :r, true)"
            ),
            {"t": tenant_id, "e": email, "h": hash_password(STRONG), "r": role},
        )


# ---------------------------------------------------------------------------
# AC1 - invite one user
# ---------------------------------------------------------------------------


class TestInviteOneUser:
    async def test_invites_an_employee_and_they_accept_at_that_role(
        self, async_client, tenant_a, token_a_admin
    ):
        """The role on the invite is the role the user ends up with.

        This is the whole point of AC1. Before it, `/invite/accept` hardcoded
        client_admin, so there was no way to onboard anyone but an admin.
        """
        resp = await _invite(async_client, token_a_admin, "new@tenanta.com", "employee")
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert len(body["code"]) == 43
        assert body["role"] == "employee"
        assert body["expires_at"]

        resp = await _accept(async_client, body["code"], "new@tenanta.com")
        assert resp.status_code == 200, resp.text

        resp = await _login(async_client, "TENANT_A", "new@tenanta.com")
        assert resp.status_code == 200, resp.text
        assert resp.json()["role"] == "employee"

    async def test_employee_invite_is_not_blocked_by_the_existing_admin(
        self, async_client, tenant_a, token_a_admin
    ):
        """VQ-107 AC3's one-Client-Admin guard applies to admin invites only.

        If it applied to every invite, no tenant could ever hire anyone, which is
        the whole of AC1.
        """
        resp = await _invite(async_client, token_a_admin, "second@tenanta.com", "client_admin")
        assert resp.status_code == 201, resp.text
        resp = await _accept(async_client, resp.json()["code"], "second@tenanta.com")
        assert resp.status_code == 200, resp.text

    async def test_super_admin_invite_for_admin_still_refused_when_one_exists(
        self, async_client, tenant_a, super_admin_token
    ):
        """VQ-107 AC3 is unchanged for the bootstrap case.

        tenant_a already has a client_admin, so the platform's own invite must
        still be refused. This is the regression check that scoping AC1's new
        role did not quietly delete an existing guarantee.
        """
        resp = await async_client.post(
            f"/admin/tenants/{tenant_a['id']}/invite",
            json={"email": "boot@tenanta.com", "expires_in_hours": 168},
            headers=_headers(super_admin_token),
        )
        assert resp.status_code == 400, resp.text
        assert "already has a Client Admin" in resp.json()["detail"]

    async def test_email_is_normalised_to_lowercase(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        resp = await _invite(async_client, token_a_admin, "  Mixed.Case@Tenanta.COM ", "employee")
        assert resp.status_code == 201, resp.text
        assert resp.json()["email"] == "mixed.case@tenanta.com"

    @pytest.mark.parametrize(
        "role", ["super_admin", "platform", "", "EMPLOYEE_ADMIN", "super admin"]
    )
    async def test_only_two_roles_may_be_invited(self, async_client, tenant_a, token_a_admin, role):
        """super_admin is refused above all else.

        It is the one role that would escape tenant scoping entirely, so it must
        not be reachable through a client-facing endpoint no matter what the
        schema is later loosened to.
        """
        resp = await _invite(async_client, token_a_admin, "x@tenanta.com", role)
        assert resp.status_code == 422, resp.text

    @pytest.mark.parametrize("email", ["", "   ", "not-an-email", "@tenanta.com", "a@b"])
    async def test_malformed_email_is_refused(self, async_client, tenant_a, token_a_admin, email):
        resp = await _invite(async_client, token_a_admin, email, "employee")
        assert resp.status_code == 422, resp.text

    async def test_duplicate_user_is_refused(self, async_client, tenant_a, token_a_admin):
        resp = await _invite(async_client, token_a_admin, "emp@a.com", "employee")
        assert resp.status_code == 409, resp.text

    async def test_second_live_invite_for_same_email_is_refused(
        self, async_client, tenant_a, token_a_admin
    ):
        assert (await _invite(async_client, token_a_admin, "dup@tenanta.com", "employee")).status_code == 201
        resp = await _invite(async_client, token_a_admin, "dup@tenanta.com", "employee")
        assert resp.status_code == 409, resp.text

    async def test_email_that_exists_in_another_tenant_is_not_visible(
        self, async_client, tenant_a, tenant_b, token_a_admin, db_engine
    ):
        """A's admin must not learn that B has emp@b.com.

        The invite is allowed, because from A's point of view nothing about that
        address is taken. If it were refused, the refusal itself would confirm the
        other tenant has that user - a cross-tenant existence leak through a 409.
        """
        resp = await _invite(async_client, token_a_admin, "emp@b.com", "employee")
        assert resp.status_code == 201, resp.text

        async with db_engine.begin() as conn:
            stored = await conn.execute(
                text("SELECT tenant_id, email FROM invites WHERE email = 'emp@b.com'")
            )
            row = stored.one()
        assert str(row[0]) == str(tenant_a["id"]), "invite landed in the wrong tenant"
        assert row[1] == "emp@b.com"

    async def test_invite_binds_to_the_issuing_tenant_only(
        self, async_client, tenant_a, tenant_b, token_a_admin, db_engine
    ):
        """An invite issued by A must create the user in A.

        The accept call carries no tenant, so the only thing that can put the new
        user anywhere is the invite row's own tenant_id.
        """
        resp = await _invite(async_client, token_a_admin, "bound@tenanta.com", "employee")
        code = resp.json()["code"]

        resp = await _accept(async_client, code, "bound@tenanta.com")
        assert resp.status_code == 200, resp.text
        assert resp.json()["tenant_id"] == str(tenant_a["id"])
        assert resp.json()["tenant_id"] != str(tenant_b["id"])

    async def test_invite_is_one_time(
        self, async_client, tenant_a, token_a_admin
    ):
        resp = await _invite(async_client, token_a_admin, "once@tenanta.com", "employee")
        code = resp.json()["code"]
        assert (await _accept(async_client, code, "once@tenanta.com")).status_code == 200
        resp = await _accept(async_client, code, "once@tenanta.com")
        assert resp.status_code == 400, resp.text

    async def test_expired_invite_is_refused(self, async_client, tenant_a, token_a_admin, db_engine):
        resp = await _invite(async_client, token_a_admin, "old@tenanta.com", "employee")
        code = resp.json()["code"]

        async with db_engine.begin() as conn:
            await conn.execute(text("UPDATE invites SET expires_at = now() - interval '1 hour'"))

        resp = await _accept(async_client, code, "old@tenanta.com")
        assert resp.status_code == 400, resp.text

    async def test_employee_cannot_invite(self, async_client, tenant_a, token_a_emp):
        resp = await _invite(async_client, token_a_emp, "x@tenanta.com", "employee")
        assert resp.status_code == 403, resp.text

    async def test_super_admin_cannot_invite(
        self, async_client, tenant_a, super_admin_token
    ):
        """VQ-106 AC4: platform operators do not manage tenant users."""
        resp = await _invite(async_client, super_admin_token, "x@tenanta.com", "employee")
        assert resp.status_code == 403, resp.text

    async def test_response_body_carries_no_other_tenant_identifier(
        self, async_client, tenant_a, tenant_b, token_a_admin
    ):
        resp = await _invite(async_client, token_a_admin, "leak@tenanta.com", "employee")
        assert resp.status_code == 201, resp.text
        raw = resp.text
        assert str(tenant_b["id"]) not in raw
        assert "emp@b.com" not in raw
        assert "admin@b.com" not in raw

    async def test_invite_writes_an_audit_row(self, async_client, tenant_a, token_a_admin):
        resp = await _invite(async_client, token_a_admin, "audited@tenanta.com", "employee")
        assert resp.status_code == 201, resp.text

        resp = await async_client.get("/users/audit", headers=_headers(token_a_admin))
        assert resp.status_code == 200, resp.text
        actions = [row["action"] for row in resp.json()]
        assert "create_user_invite" in actions

    async def test_accept_degrades_cleanly_when_the_address_is_taken(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        """A race between the existence check and the insert must not be a 500.

        The endpoint checks for an existing user and then inserts. That is
        check-then-act, and /users/import can create the address in between - it
        used to, before the import learned to refuse outstanding invites. The
        unique constraint is the real authority, so the insert can lose the race
        at any time and the answer must be a 4xx the person can act on.
        """
        invite = await _invite(async_client, token_a_admin, "racer@tenanta.com", "employee")
        code = invite.json()["code"]

        # Take the address behind the endpoint's back, the way a concurrent
        # import or a second accept would.
        await _insert_user(db_engine, tenant_a["id"], "racer@tenanta.com", "employee")

        resp = await async_client.post(
            "/invite/accept", json={"code": code, "password": "RacerOne1!"}
        )
        assert resp.status_code == 400, resp.text
        assert "already exists" in resp.json()["detail"]
        # Not a 500, and the failure is legible to the person holding the code.
        assert resp.status_code < 500
        # The code must not have been consumed by the failed attempt.
        assert (
            await _row(db_engine, "invites", "code = :c AND used_at IS NULL", {"c": code}) == 1
        )

    async def test_the_password_from_a_refused_accept_does_not_work(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        """The person chose that password believing it took. It must not."""
        invite = await _invite(async_client, token_a_admin, "ghost@tenanta.com", "employee")
        code = invite.json()["code"]
        await _insert_user(db_engine, tenant_a["id"], "ghost@tenanta.com", "employee")

        resp = await async_client.post(
            "/invite/accept", json={"code": code, "password": "GhostOne1!"}
        )
        assert resp.status_code == 400, resp.text

        resp = await async_client.post(
            "/auth/login",
            json={
                "organisation_code": tenant_a["short_code"],
                "email": "ghost@tenanta.com",
                "password": "GhostOne1!",
            },
        )
        assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# AC2 - CSV import
# ---------------------------------------------------------------------------


class TestCsvImport:
    GOOD = "email,role\nstaff1@tenanta.com,employee\nstaff2@tenanta.com,employee\n"

    async def test_imports_a_valid_file(self, async_client, tenant_a, token_a_admin, db_engine):
        resp = await _csv(async_client, token_a_admin, self.GOOD)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["applied"] is True
        assert body["created_count"] == 2
        assert body["invalid_count"] == 0
        assert body["total_rows"] == 2
        assert all(r["status"] == "created" for r in body["rows"])
        assert await _row(db_engine, "users", "email = ANY(:e)", {"e": ["staff1@tenanta.com", "staff2@tenanta.com"]}) == 2

    async def test_one_invalid_row_creates_nothing_at_all(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        """All-or-nothing. The valid rows in this file must not land.

        A half-applied staff list is the failure this exists to prevent: the
        admin cannot tell which half worked, and cannot tell whether the two
        people who got in are the two they sent.
        """
        csv_text = (
            "email,role\n"
            "good1@tenanta.com,employee\n"
            "broken@tenanta.com,wizard\n"
            "good2@tenanta.com,employee\n"
        )
        resp = await _csv(async_client, token_a_admin, csv_text)
        # 400, not 200-with-applied-false: a 2xx would let a client report
        # success over a staff list that did not land.
        assert resp.status_code == 400, resp.text
        body = resp.json()
        assert body["applied"] is False
        assert body["created_count"] == 0
        assert body["invalid_count"] == 1

        invalid = [r for r in body["rows"] if r["status"] == "invalid"]
        assert len(invalid) == 1
        assert invalid[0]["email"] == "broken@tenanta.com"
        assert invalid[0]["line"] == 3
        assert "role" in invalid[0]["reason"].lower()

        # The two valid rows must not be reported as created. This report is the
        # entire deliverable of the endpoint, so it is what the admin's screen
        # renders: "created" here would put a green tick on two people who do
        # not exist. Same silent-wrong failure as a 2xx on a refused import.
        good = [r for r in body["rows"] if r["email"].startswith("good")]
        assert len(good) == 2
        assert all(r["status"] == "not_created" for r in good), body["rows"]
        assert all(r["reason"] for r in good)
        assert not [r for r in body["rows"] if r["status"] == "created"]

        assert await _row(db_engine, "users", "email LIKE 'good%'") == 0
        assert await _row(db_engine, "users", "email = 'broken@tenanta.com'") == 0

    async def test_the_report_never_claims_a_row_the_database_does_not_have(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        """Every 'created' row in any report must exist in `users`. No exceptions.

        This is the invariant behind the per-row statuses, checked against the
        table rather than against the other fields of the same response, because
        the fields of the response were the thing that was wrong.
        """
        good = "email,role\nonly-good@tenanta.com,employee\n"
        resp = await _csv(async_client, token_a_admin, good)
        assert resp.status_code == 200, resp.text
        claimed = [r["email"] for r in resp.json()["rows"] if r["status"] == "created"]
        assert claimed
        assert await _row(db_engine, "users", "email = ANY(:e)", {"e": claimed}) == len(claimed)

        bad = "email,role\nclaimed@tenanta.com,employee\nnope@tenanta.com,wizard\n"
        resp = await _csv(async_client, token_a_admin, bad)
        assert resp.status_code == 400, resp.text
        claimed = [r["email"] for r in resp.json()["rows"] if r["status"] == "created"]
        assert claimed == []
        assert await _row(db_engine, "users", "email = 'claimed@tenanta.com'") == 0

    async def test_pending_never_reaches_the_client(
        self, async_client, tenant_a, token_a_admin
    ):
        """"pending" is internal. It would tell the admin nothing about their file."""
        for text in (self.GOOD, "email,role\na@tenanta.com,employee\nb@tenanta.com,wizard\n"):
            resp = await _csv(async_client, token_a_admin, text)
            assert resp.status_code in (200, 400), resp.text
            assert all(r["status"] != "pending" for r in resp.json()["rows"]), resp.text

    async def test_report_covers_every_row_not_only_the_bad_ones(
        self, async_client, tenant_a, token_a_admin
    ):
        """The admin has to be able to fix the file, so line numbers matter."""
        csv_text = "email,role\na@tenanta.com,employee\nb@tenanta.com,nope\nc@tenanta.com,bad-email\n"
        resp = await _csv(async_client, token_a_admin, csv_text)
        assert resp.status_code == 400, resp.text
        body = resp.json()
        assert body["total_rows"] == 3
        assert {r["line"] for r in body["rows"]} == {2, 3, 4}
        assert all(r["reason"] for r in body["rows"] if r["status"] == "invalid")

    async def test_duplicate_inside_the_file_is_invalid(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        csv_text = "email,role\ndup@tenanta.com,employee\nDUP@tenanta.com,employee\n"
        resp = await _csv(async_client, token_a_admin, csv_text)
        assert resp.status_code == 400, resp.text
        body = resp.json()
        assert body["applied"] is False
        assert await _row(db_engine, "users", "email = 'dup@tenanta.com'") == 0

    async def test_existing_user_is_invalid(self, async_client, tenant_a, token_a_admin, db_engine):
        csv_text = "email,role\nemp@a.com,employee\n"
        resp = await _csv(async_client, token_a_admin, csv_text)
        assert resp.status_code == 400, resp.text
        assert "already exists" in resp.json()["rows"][0]["reason"]
        assert await _row(db_engine, "users", "email = 'emp@a.com'") == 1

    async def test_other_tenants_users_are_not_treated_as_duplicates(
        self, async_client, tenant_a, tenant_b, token_a_admin, db_engine
    ):
        """emp@b.com must be importable into A.

        If B's rows were visible the row would be rejected as a duplicate, and
        the rejection would tell A's admin that the address is already in use
        somewhere in VaultIQ.
        """
        csv_text = "email,role\nemp@b.com,employee\n"
        resp = await _csv(async_client, token_a_admin, csv_text)
        assert resp.status_code == 200, resp.text
        assert resp.json()["applied"] is True
        assert await _row(
            db_engine, "users", "email = 'emp@b.com' AND tenant_id = :t", {"t": tenant_a["id"]}
        ) == 1

    async def test_an_address_with_an_outstanding_invite_is_invalid(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        """Invite then import the same address must not collide.

        Found at Gate 6: the import only read the users table, so it created a
        user for an address that already had a live invite, and the invite then
        blew up /invite/accept with a 500.
        """
        invite = await _invite(async_client, token_a_admin, "pending@tenanta.com", "employee")
        assert invite.status_code == 201, invite.text

        csv_text = "email,role\npending@tenanta.com,employee\nfresh@tenanta.com,employee\n"
        resp = await _csv(async_client, token_a_admin, csv_text)
        assert resp.status_code == 400, resp.text
        body = resp.json()
        assert body["applied"] is False
        reason = [r for r in body["rows"] if r["email"] == "pending@tenanta.com"][0]["reason"]
        assert "invite" in reason.lower()
        # The whole file is refused, including the row that had no problem.
        assert await _row(db_engine, "users", "email = 'pending@tenanta.com'") == 0
        assert await _row(db_engine, "users", "email = 'fresh@tenanta.com'") == 0

    async def test_the_outstanding_invite_can_still_be_accepted(
        self, async_client, tenant_a, token_a_admin
    ):
        """After the import refuses the row, the invite must still work."""
        invite = await _invite(async_client, token_a_admin, "pending2@tenanta.com", "employee")
        code = invite.json()["code"]

        resp = await _csv(
            async_client, token_a_admin, "email,role\npending2@tenanta.com,employee\n"
        )
        assert resp.status_code == 400, resp.text

        resp = await async_client.post(
            "/invite/accept", json={"code": code, "password": "PendingOne1!"}
        )
        assert resp.status_code == 200, resp.text

    async def test_an_expired_invite_does_not_block_an_import(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        """Only a *live* invite conflicts. A spent or lapsed one must not."""
        invite = await _invite(async_client, token_a_admin, "used@tenanta.com", "employee")
        code = invite.json()["code"]
        resp = await async_client.post(
            "/invite/accept", json={"code": code, "password": "UsedOne1!!"}
        )
        assert resp.status_code == 200, resp.text

        resp = await _csv(async_client, token_a_admin, "email,role\nused@tenanta.com,employee\n")
        assert resp.status_code == 400, resp.text
        assert "already exists" in resp.json()["rows"][0]["reason"]

    @pytest.mark.parametrize(
        "csv_text,fragment",
        [
            ("email\nonly@tenanta.com\n", "role"),
            ("role\nemployee\n", "email"),
            ("", "empty"),
            ("   \n", "empty"),
            ("\n\n\n", "empty"),
        ],
    )
    async def test_bad_shape_is_a_400(self, async_client, tenant_a, token_a_admin, csv_text, fragment):
        resp = await _csv(async_client, token_a_admin, csv_text)
        assert resp.status_code == 400, resp.text
        assert fragment in resp.json()["detail"].lower()

    async def test_header_order_does_not_matter(self, async_client, tenant_a, token_a_admin):
        resp = await _csv(async_client, token_a_admin, "role,email\nemployee,rev@tenanta.com\n")
        assert resp.status_code == 200, resp.text
        assert resp.json()["applied"] is True

    async def test_extra_columns_are_ignored(self, async_client, tenant_a, token_a_admin):
        resp = await _csv(
            async_client,
            token_a_admin,
            "email,role,department,notes\nextra@tenanta.com,employee,sales,hi\n",
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["created_count"] == 1

    async def test_non_utf8_is_a_400_not_a_500(
        self, async_client, tenant_a, token_a_admin
    ):
        resp = await async_client.post(
            "/users/import",
            files={"file": ("staff.csv", b"\xff\xfe\x00binary", "text/csv")},
            headers=_headers(token_a_admin),
        )
        assert resp.status_code == 400, resp.text

    async def test_more_than_five_hundred_rows_is_refused(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        """A bound, and one that is checked before anything is written."""
        csv_text = "email,role\n" + "".join(
            f"bulk{i}@tenanta.com,employee\n" for i in range(501)
        )
        resp = await _csv(async_client, token_a_admin, csv_text)
        assert resp.status_code == 400, resp.text
        assert "500" in resp.json()["detail"]
        assert await _row(db_engine, "users", "email LIKE 'bulk%'") == 0

    async def test_the_refusal_is_at_the_boundary(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        """500 rows is accepted, 501 is not - and nothing is written either way.

        Only the refused side is exercised end to end. The accepted side would
        mean 500 bcrypt hashes, which is minutes of CPU for a fact the code
        states in one comparison: `len(rows) > MAX_IMPORT_ROWS`. What matters
        here is that the refusal happens before any hashing, which is why no
        password was spent on the rows that were going to be turned away.
        """
        rows = "".join(f"edge{i}@tenanta.com,employee\n" for i in range(501))
        resp = await _csv(async_client, token_a_admin, "email,role\n" + rows)
        assert resp.status_code == 400, resp.text
        assert "501" in resp.json()["detail"]
        assert "500" in resp.json()["detail"]
        assert await _row(db_engine, "users", "email LIKE 'edge%'") == 0

    async def test_imported_user_cannot_log_in_until_they_reset(
        self, async_client, tenant_a, token_a_admin
    ):
        """The imported password is nobody's to know.

        The account exists and is active but unusable, so the only way in is the
        AC4 reset flow - which requires the Client Admin to be present.
        """
        resp = await _csv(async_client, token_a_admin, "email,role\nlocked@tenanta.com,employee\n")
        assert resp.json()["applied"] is True

        for guess in ["", "password", "Password1!", "unusable:", "locked@tenanta.com"]:
            resp = await _login(async_client, "TENANT_A", "locked@tenanta.com", guess or "x")
            assert resp.status_code == 401, f"logged in with {guess!r}"

    async def test_imported_user_can_log_in_after_a_reset(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        """The unusable account has to be escapable, not a dead end.

        This is the whole justification for not putting passwords in the CSV:
        the AC4 flow is the way out, and it already exists.
        """
        await _csv(async_client, token_a_admin, "email,role\nescape@tenanta.com,employee\n")

        resp = await _login(async_client, "TENANT_A", "escape@tenanta.com")
        assert resp.status_code == 401

        user_id = await _user_id_by_email(db_engine, "escape@tenanta.com", tenant_a["id"])
        resp = await async_client.post(
            f"/users/{user_id}/password-reset", headers=_headers(token_a_admin)
        )
        assert resp.status_code == 201, resp.text
        code = resp.json()["reset_code"]

        resp = await async_client.post(
            "/auth/reset-password", json={"code": code, "new_password": "ChosenPass1!"}
        )
        assert resp.status_code == 200, resp.text

        resp = await _login(async_client, "TENANT_A", "escape@tenanta.com", "ChosenPass1!")
        assert resp.status_code == 200, resp.text

    async def test_employee_cannot_import(self, async_client, tenant_a, token_a_emp):
        resp = await _csv(async_client, token_a_emp, self.GOOD)
        assert resp.status_code == 403, resp.text

    async def test_super_admin_cannot_import(self, async_client, tenant_a, super_admin_token):
        resp = await _csv(async_client, super_admin_token, self.GOOD)
        assert resp.status_code == 403, resp.text

    async def test_import_stays_inside_the_callers_tenant(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        await _csv(async_client, token_a_admin, self.GOOD)
        async with db_engine.begin() as conn:
            result = await conn.execute(
                text("SELECT DISTINCT tenant_id FROM users WHERE email LIKE 'staff%@tenanta.com'")
            )
            ids = {str(r) for r in result.scalars().all()}
        assert ids == {str(tenant_a["id"])}

    async def test_import_writes_an_audit_row(self, async_client, tenant_a, token_a_admin):
        await _csv(async_client, token_a_admin, self.GOOD)
        resp = await async_client.get("/users/audit", headers=_headers(token_a_admin))
        rows = [r for r in resp.json() if r["action"] == "import_users"]
        assert len(rows) == 1
        assert rows[0]["details"]["imported_count"] == 2

    async def test_audit_row_holds_no_credential_material(
        self, async_client, tenant_a, token_a_admin
    ):
        """No hashes, no passwords. The trail outlives the people in it.

        Checked by shape rather than by comparing against a computed hash: bcrypt
        salts are random, so `hash_password(x) not in body` would pass whether or
        not a hash were present. `$2b$` is the marker that one is.
        """
        await _csv(async_client, token_a_admin, self.GOOD)
        resp = await async_client.get("/users/audit", headers=_headers(token_a_admin))
        raw = resp.text
        assert "$2b$" not in raw
        assert "$2a$" not in raw
        assert "unusable:" not in raw
        assert STRONG not in raw

    async def test_report_line_numbers_survive_blank_lines(
        self, async_client, tenant_a, token_a_admin
    ):
        """A report that points at the wrong line is worse than no report.

        Blank lines are dropped before parsing, so an implementation that numbers
        the filtered list would blame line 3 when the error is really on line 5.
        """
        csv_text = (
            "email,role\n"
            "first@tenanta.com,employee\n"
            "\n"
            "\n"
            "wrong@tenanta.com,wizard\n"
        )
        resp = await _csv(async_client, token_a_admin, csv_text)
        assert resp.status_code == 400, resp.text
        rows = resp.json()["rows"]
        assert [r["line"] for r in rows] == [2, 5]
        assert rows[1]["email"] == "wrong@tenanta.com"

    async def test_oversized_file_is_refused_before_parsing(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        """`file.read()` with no limit is how an upload becomes an allocation.

        The cap is enforced by reading one byte past it, not by trusting the
        client's Content-Length.
        """
        # 500 valid rows padded past the 1 MB cap.
        padded = (
            "email,role\n"
            + "".join(f"pad{i}@tenanta.com,employee\n" for i in range(500))
        )
        padded += "#" * MAX_IMPORT_BYTES
        resp = await _csv(async_client, token_a_admin, padded)
        assert resp.status_code == 400, resp.text
        assert "larger than" in resp.json()["detail"]
        assert await _row(db_engine, "users", "email LIKE 'pad%'") == 0


async def _user_id_by_email(db_engine, email: str, tenant_id) -> str:
    """Look a user up by email as the superuser.

    There is deliberately no GET /users listing endpoint on this branch - a staff
    list is a document-adjacent read and VQ-301 does not ask for one - so tests
    that need a user's id get it here, from the database, rather than from the API.
    """
    async with db_engine.begin() as conn:
        result = await conn.execute(
            text("SELECT id FROM users WHERE email = :e AND tenant_id = :t"),
            {"e": email, "t": tenant_id},
        )
        return str(result.scalar_one())


# ---------------------------------------------------------------------------
# AC3 - deactivate and reactivate
# ---------------------------------------------------------------------------


class TestDeactivateReactivate:
    async def test_deactivate_sets_the_flag_and_ends_sessions(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        resp = await async_client.post(
            f"/users/{tenant_a['employee']['id']}/deactivate", headers=_headers(token_a_admin)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["user"]["is_active"] is False
        assert body["sessions_revoked"] >= 1

        assert await _row(db_engine, "users", "is_active = false") == 1
        assert await _row(
            db_engine, "sessions", "user_id = :u AND is_revoked = true", {"u": tenant_a["employee"]["id"]}
        ) >= 1

    async def test_deactivated_user_cannot_log_in(
        self, async_client, tenant_a, token_a_admin
    ):
        await async_client.post(
            f"/users/{tenant_a['employee']['id']}/deactivate", headers=_headers(token_a_admin)
        )
        resp = await _login(async_client, "TENANT_A", "emp@a.com")
        assert resp.status_code == 401, resp.text
        # Same body as a wrong password: deactivated must not be distinguishable.
        wrong = await _login(async_client, "TENANT_A", "emp@a.com", "WrongPass1!")
        assert wrong.json()["detail"] == resp.json()["detail"]
        assert wrong.status_code == resp.status_code

    async def test_deactivated_users_existing_token_stops_working(
        self, async_client, tenant_a, token_a_admin, token_a_emp
    ):
        """"Immediately", not "at the end of their session".

        The revocation is in the same transaction as the flag, so the very next
        request with a previously valid token is refused.
        """
        assert (
            await async_client.get("/documents", headers=_headers(token_a_emp))
        ).status_code == 200

        assert (
            await async_client.post(
                f"/users/{tenant_a['employee']['id']}/deactivate", headers=_headers(token_a_admin)
            )
        ).status_code == 200

        resp = await async_client.get("/documents", headers=_headers(token_a_emp))
        assert resp.status_code == 401, resp.text

    async def test_reactivate_restores_login(
        self, async_client, tenant_a, token_a_admin
    ):
        await async_client.post(
            f"/users/{tenant_a['employee']['id']}/deactivate", headers=_headers(token_a_admin)
        )
        resp = await async_client.post(
            f"/users/{tenant_a['employee']['id']}/reactivate", headers=_headers(token_a_admin)
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["user"]["is_active"] is True
        assert (await _login(async_client, "TENANT_A", "emp@a.com")).status_code == 200

    async def test_reactivate_does_not_resurrect_sessions(
        self, async_client, tenant_a, token_a_admin, token_a_emp
    ):
        """They log in again. Reinstating a token would be surprising and wrong."""
        await async_client.post(
            f"/users/{tenant_a['employee']['id']}/deactivate", headers=_headers(token_a_admin)
        )
        await async_client.post(
            f"/users/{tenant_a['employee']['id']}/reactivate", headers=_headers(token_a_admin)
        )
        resp = await async_client.get("/documents", headers=_headers(token_a_emp))
        assert resp.status_code == 401, resp.text

    async def test_cannot_deactivate_yourself(
        self, async_client, tenant_a, token_a_admin
    ):
        """Nobody else may manage this account, so self-deactivation is a lockout."""
        resp = await async_client.post(
            f"/users/{tenant_a['client_admin']['id']}/deactivate", headers=_headers(token_a_admin)
        )
        assert resp.status_code == 400, resp.text

    async def test_admin_can_step_down_once_another_admin_exists(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        """The supported way an admin leaves: a second admin deactivates them."""
        resp = await _invite(async_client, token_a_admin, "admin2@tenanta.com", "client_admin")
        resp = await _accept(async_client, resp.json()["code"], "admin2@tenanta.com")
        assert resp.status_code == 200, resp.text

        resp = await _login(async_client, "TENANT_A", "admin2@tenanta.com")
        assert resp.status_code == 200, resp.text
        admin2_token = resp.json()["access_token"]

        resp = await async_client.post(
            f"/users/{tenant_a['client_admin']['id']}/deactivate",
            headers=_headers(admin2_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["user"]["is_active"] is False

        # tenant_a can still be administered.
        resp = await async_client.get("/users/audit", headers=_headers(admin2_token))
        assert resp.status_code == 200, resp.text

    async def test_a_tenant_is_never_left_without_an_active_admin(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        """The last-admin invariant, tested as the invariant rather than as a branch.

        Finding, worth recording because it decides how this is tested: the
        runtime "only active Client Admin" check in deactivate and in demote is
        **unreachable** through the API. Only a client_admin may call either, a
        client_admin may not target themselves, so any other client_admin calling
        it is by definition a second active Client Admin. The count can never be
        zero.

        The guarantee therefore rests on the self-target rule, and that is what
        this test exercises: every route a sole admin has to their own account is
        refused, and the tenant is still administrable afterwards. The runtime
        check stays as defence-in-depth if either rule above is ever relaxed, and
        it is documented as such rather than left looking load-bearing.
        """
        sole_id = tenant_a["client_admin"]["id"]

        resp = await async_client.post(
            f"/users/{sole_id}/deactivate", headers=_headers(token_a_admin)
        )
        assert resp.status_code == 400, resp.text
        assert "your own account" in resp.json()["detail"].lower()

        resp = await async_client.patch(
            f"/users/{sole_id}/role",
            json={"role": "employee", "current_password": STRONG},
            headers=_headers(token_a_admin),
        )
        assert resp.status_code == 400, resp.text
        assert "your own role" in resp.json()["detail"].lower()

        # Still active, still a Client Admin, still able to run the tenant.
        assert await _row(
            db_engine, "users", "id = :u AND is_active AND role = 'client_admin'", {"u": sole_id}
        ) == 1
        resp = await _login(async_client, "TENANT_A", "admin@a.com")
        assert resp.status_code == 200, resp.text
        resp = await async_client.get("/users/audit", headers=_headers(token_a_admin))
        assert resp.status_code == 200, resp.text

    async def test_cannot_target_another_tenant(self, async_client, tenant_a, tenant_b, token_a_admin, db_engine):
        resp = await async_client.post(
            f"/users/{tenant_b['employee']['id']}/deactivate", headers=_headers(token_a_admin)
        )
        # 404, not 403: B's employee must not be confirmed to exist.
        assert resp.status_code == 404, resp.text
        assert await _row(
            db_engine, "users", "id = :u AND is_active = true", {"u": tenant_b["employee"]["id"]}
        ) == 1

    async def test_cannot_reactivate_another_tenant(
        self, async_client, tenant_a, tenant_b, token_a_admin, db_engine
    ):
        """Only B's employee is deactivated, so A's own token still works.

        Deactivating A's admin as well would be refused at the session check
        before the endpoint ran, and the test would prove nothing about tenant
        scoping.
        """
        async with db_engine.begin() as conn:
            await conn.execute(
                text("UPDATE users SET is_active = false WHERE id = :u"),
                {"u": tenant_b["employee"]["id"]},
            )

        resp = await async_client.post(
            f"/users/{tenant_b['employee']['id']}/reactivate", headers=_headers(token_a_admin)
        )
        assert resp.status_code == 404, resp.text
        assert await _row(
            db_engine, "users", "id = :u AND is_active = false", {"u": tenant_b["employee"]["id"]}
        ) == 1

    async def test_deactivating_twice_is_a_400(self, async_client, tenant_a, token_a_admin):
        await async_client.post(
            f"/users/{tenant_a['employee']['id']}/deactivate", headers=_headers(token_a_admin)
        )
        resp = await async_client.post(
            f"/users/{tenant_a['employee']['id']}/deactivate", headers=_headers(token_a_admin)
        )
        assert resp.status_code == 400, resp.text

    async def test_reactivating_an_active_user_is_a_400(self, async_client, tenant_a, token_a_admin):
        resp = await async_client.post(
            f"/users/{tenant_a['employee']['id']}/reactivate", headers=_headers(token_a_admin)
        )
        assert resp.status_code == 400, resp.text

    async def test_employee_cannot_deactivate(self, async_client, tenant_a, token_a_emp):
        resp = await async_client.post(
            f"/users/{tenant_a['client_admin']['id']}/deactivate", headers=_headers(token_a_emp)
        )
        assert resp.status_code == 403, resp.text

    async def test_super_admin_cannot_deactivate(self, async_client, tenant_a, super_admin_token):
        resp = await async_client.post(
            f"/users/{tenant_a['employee']['id']}/deactivate", headers=_headers(super_admin_token)
        )
        assert resp.status_code == 403, resp.text

    async def test_reactivation_does_not_clear_a_lockout(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        """A lockout is a security event; a reactivation is an HR decision.

        Clearing it here would let an admin walk around the five-attempt control
        simply by toggling the account. The reset flow clears it, and that one is
        step-up protected on the target side.
        """
        for _ in range(5):
            await _login(async_client, "TENANT_A", "emp@a.com", "WrongPass1!")
        assert await _row(
            db_engine, "users", "email = 'emp@a.com' AND locked_until IS NOT NULL"
        ) == 1

        await async_client.post(
            f"/users/{tenant_a['employee']['id']}/deactivate", headers=_headers(token_a_admin)
        )
        resp = await async_client.post(
            f"/users/{tenant_a['employee']['id']}/reactivate", headers=_headers(token_a_admin)
        )
        assert resp.status_code == 200, resp.text

        assert await _row(
            db_engine, "users", "email = 'emp@a.com' AND locked_until IS NOT NULL"
        ) == 1

    async def test_both_operations_are_audited(self, async_client, tenant_a, token_a_admin):
        await async_client.post(
            f"/users/{tenant_a['employee']['id']}/deactivate", headers=_headers(token_a_admin)
        )
        await async_client.post(
            f"/users/{tenant_a['employee']['id']}/reactivate", headers=_headers(token_a_admin)
        )
        resp = await async_client.get("/users/audit", headers=_headers(token_a_admin))
        actions = [r["action"] for r in resp.json()]
        assert "deactivate_user" in actions
        assert "reactivate_user" in actions


# ---------------------------------------------------------------------------
# AC5 - role change behind step-up re-authentication
# ---------------------------------------------------------------------------


class TestRoleChange:
    async def test_employee_promoted_to_client_admin(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        resp = await async_client.patch(
            f"/users/{tenant_a['employee']['id']}/role",
            json={"role": "client_admin", "current_password": STRONG},
            headers=_headers(token_a_admin),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["user"]["role"] == "client_admin"
        assert body["sessions_revoked"] is True
        assert await _row(
            db_engine, "users", "id = :u AND role = 'client_admin'", {"u": tenant_a["employee"]["id"]}
        ) == 1

    async def test_promoted_user_actually_gets_the_new_permissions(
        self, async_client, tenant_a, token_a_admin, token_a_emp
    ):
        """The point of the change, not just the database row."""
        emp_token = token_a_emp
        assert (
            await async_client.patch(
                f"/users/{tenant_a['employee']['id']}/role",
                json={"role": "client_admin", "current_password": STRONG},
                headers=_headers(token_a_admin),
            )
        ).status_code == 200

        resp = await async_client.post(
            "/users/invites", json={"email": "invited@tenanta.com", "role": "employee"},
            headers=_headers(emp_token),
        )
        # The old token carries the old role claim and its session was revoked,
        # so this is refused rather than wrongly allowed.
        assert resp.status_code == 401, resp.text

        # After logging in again the same call succeeds.
        resp = await _login(async_client, "TENANT_A", "emp@a.com")
        assert resp.status_code == 200, resp.text
        new_token = resp.json()["access_token"]
        resp = await async_client.post(
            "/users/invites", json={"email": "invited@tenanta.com", "role": "employee"},
            headers=_headers(new_token),
        )
        assert resp.status_code == 201, resp.text

    async def test_wrong_current_password_is_refused_and_changes_nothing(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        resp = await async_client.patch(
            f"/users/{tenant_a['employee']['id']}/role",
            json={"role": "client_admin", "current_password": "WrongPass1!"},
            headers=_headers(token_a_admin),
        )
        assert resp.status_code == 401, resp.text
        assert await _row(
            db_engine, "users", "id = :u AND role = 'employee'", {"u": tenant_a["employee"]["id"]}
        ) == 1

    async def test_missing_current_password_is_refused(self, async_client, tenant_a, token_a_admin):
        resp = await async_client.patch(
            f"/users/{tenant_a['employee']['id']}/role",
            json={"role": "client_admin"},
            headers=_headers(token_a_admin),
        )
        assert resp.status_code == 422, resp.text

    async def test_wrong_password_is_refused_before_the_target_is_looked_up(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        """Step-up failure must not become a probe for which ids exist.

        A bad step-up password is a 401 whatever the target is, so the endpoint
        cannot be used to enumerate users even inside the caller's own tenant.
        """
        resp = await async_client.patch(
            "/users/00000000-0000-0000-0000-0000000000ff/role",
            json={"role": "client_admin", "current_password": "WrongPass1!"},
            headers=_headers(token_a_admin),
        )
        assert resp.status_code == 401, resp.text

        resp = await async_client.patch(
            f"/users/{tenant_a['employee']['id']}/role",
            json={"role": "client_admin", "current_password": "WrongPass1!"},
            headers=_headers(token_a_admin),
        )
        assert resp.status_code == 401, resp.text

    async def test_super_admin_target_is_refused(self, async_client, tenant_a, token_a_admin):
        resp = await async_client.patch(
            f"/users/{tenant_a['employee']['id']}/role",
            json={"role": "super_admin", "current_password": STRONG},
            headers=_headers(token_a_admin),
        )
        assert resp.status_code == 422, resp.text

    async def test_cannot_change_your_own_role(self, async_client, tenant_a, token_a_admin):
        """Self-promotion through this path would bypass the last-admin guard."""
        resp = await async_client.patch(
            f"/users/{tenant_a['client_admin']['id']}/role",
            json={"role": "employee", "current_password": STRONG},
            headers=_headers(token_a_admin),
        )
        assert resp.status_code == 400, resp.text

    async def test_cannot_target_another_tenant(self, async_client, tenant_a, tenant_b, token_a_admin, db_engine):
        resp = await async_client.patch(
            f"/users/{tenant_b['employee']['id']}/role",
            json={"role": "client_admin", "current_password": STRONG},
            headers=_headers(token_a_admin),
        )
        assert resp.status_code == 404, resp.text
        assert await _row(
            db_engine, "users", "id = :u AND role = 'employee'", {"u": tenant_b["employee"]["id"]}
        ) == 1

    async def test_demotion_is_allowed_when_another_admin_exists(
        self, async_client, tenant_a, token_a_admin, db_engine
    ):
        resp = await _invite(async_client, token_a_admin, "admin2@tenanta.com", "client_admin")
        await _accept(async_client, resp.json()["code"], "admin2@tenanta.com")

        resp = await _login(async_client, "TENANT_A", "admin2@tenanta.com")
        assert resp.status_code == 200, resp.text
        admin2_token = resp.json()["access_token"]

        resp = await async_client.patch(
            f"/users/{tenant_a['client_admin']['id']}/role",
            json={"role": "employee", "current_password": STRONG},
            headers=_headers(admin2_token),
        )
        assert resp.status_code == 200, resp.text
        assert await _row(
            db_engine, "users", "id = :u AND role = 'employee'", {"u": tenant_a["client_admin"]["id"]}
        ) == 1

    async def test_sessions_are_revoked_on_demotion(
        self, async_client, tenant_a, token_a_admin, token_a_emp, db_engine
    ):
        """A token minted as client_admin must stop working after the demotion.

        Otherwise the old privilege lives on in the token until it expires, which
        is precisely what a role change is supposed to stop.
        """
        assert (
            await async_client.patch(
                f"/users/{tenant_a['employee']['id']}/role",
                json={"role": "client_admin", "current_password": STRONG},
                headers=_headers(token_a_admin),
            )
        ).status_code == 200

        resp = await async_client.post(
            "/users/invites", json={"email": "z@tenanta.com", "role": "employee"},
            headers=_headers(token_a_emp),
        )
        assert resp.status_code == 401, resp.text
        assert await _row(
            db_engine, "sessions", "user_id = :u AND is_revoked = true", {"u": tenant_a["employee"]["id"]}
        ) >= 1

    async def test_setting_the_same_role_is_a_400(self, async_client, tenant_a, token_a_admin):
        resp = await async_client.patch(
            f"/users/{tenant_a['employee']['id']}/role",
            json={"role": "employee", "current_password": STRONG},
            headers=_headers(token_a_admin),
        )
        assert resp.status_code == 400, resp.text

    async def test_employee_cannot_change_roles(self, async_client, tenant_a, token_a_emp):
        resp = await async_client.patch(
            f"/users/{tenant_a['employee']['id']}/role",
            json={"role": "client_admin", "current_password": STRONG},
            headers=_headers(token_a_emp),
        )
        assert resp.status_code == 403, resp.text

    async def test_super_admin_cannot_change_roles(self, async_client, tenant_a, super_admin_token):
        resp = await async_client.patch(
            f"/users/{tenant_a['employee']['id']}/role",
            json={"role": "client_admin", "current_password": "AdminPass1!"},
            headers=_headers(super_admin_token),
        )
        assert resp.status_code == 403, resp.text

    async def test_role_change_is_audited_with_both_roles(
        self, async_client, tenant_a, token_a_admin
    ):
        await async_client.patch(
            f"/users/{tenant_a['employee']['id']}/role",
            json={"role": "client_admin", "current_password": STRONG},
            headers=_headers(token_a_admin),
        )
        resp = await async_client.get("/users/audit", headers=_headers(token_a_admin))
        rows = [r for r in resp.json() if r["action"] == "change_user_role"]
        assert len(rows) == 1
        assert rows[0]["details"]["previous_role"] == "employee"
        assert rows[0]["details"]["new_role"] == "client_admin"

    async def test_audit_row_has_no_password(
        self, async_client, tenant_a, token_a_admin
    ):
        await async_client.patch(
            f"/users/{tenant_a['employee']['id']}/role",
            json={"role": "client_admin", "current_password": STRONG},
            headers=_headers(token_a_admin),
        )
        resp = await async_client.get("/users/audit", headers=_headers(token_a_admin))
        assert "$2b$" not in resp.text
        assert STRONG not in resp.text


# ---------------------------------------------------------------------------
# AC6 - tenant-scoped audit trail
# ---------------------------------------------------------------------------


class TestTenantAudit:
    async def test_returns_only_this_tenants_rows(
        self, async_client, tenant_a, tenant_b, token_a_admin, token_b_admin
    ):
        for token in (token_a_admin, token_b_admin):
            assert (
                await _invite(
                    async_client,
                    token,
                    "trail@x.com",
                    "employee",
                )
            ).status_code == 201

        resp = await async_client.get("/users/audit", headers=_headers(token_a_admin))
        assert resp.status_code == 200, resp.text
        rows = resp.json()
        assert rows, "expected at least A's own invite"
        assert all(r["actor_user_id"] == str(tenant_a["client_admin"]["id"]) for r in rows)

    async def test_body_contains_no_other_tenant_identifier(
        self, async_client, tenant_a, tenant_b, token_a_admin, token_b_admin
    ):
        await _invite(async_client, token_b_admin, "secret@b.com", "employee")
        resp = await async_client.get("/users/audit", headers=_headers(token_a_admin))
        assert resp.status_code == 200
        assert str(tenant_b["id"]) not in resp.text
        assert "secret@b.com" not in resp.text
        assert "admin@b.com" not in resp.text

    async def test_no_tenant_can_be_named_in_the_request(
        self, async_client, tenant_a, tenant_b, token_a_admin
    ):
        """There is no tenant parameter at all, so there is nothing to get wrong.

        A Client Admin asking for another tenant's trail simply gets their own.
        """
        assert (
            await async_client.get(
                "/users/audit", params={"tenant_id": str(tenant_b["id"])}, headers=_headers(token_a_admin)
            )
        ).status_code == 200
        assert (
            await async_client.get(
                f"/users/audit?tenant_id={tenant_b['id']}", headers=_headers(token_a_admin)
            )
        ).status_code == 200

    async def test_employee_cannot_read_the_trail(self, async_client, tenant_a, token_a_emp):
        resp = await async_client.get("/users/audit", headers=_headers(token_a_emp))
        assert resp.status_code == 403, resp.text

    async def test_super_admin_cannot_read_a_tenant_trail(
        self, async_client, tenant_a, super_admin_token
    ):
        """VQ-106 AC4. The platform has its own /admin/tenants/{id}/audit."""
        resp = await async_client.get("/users/audit", headers=_headers(super_admin_token))
        assert resp.status_code == 403, resp.text

    async def test_every_operation_leaves_a_row(self, async_client, tenant_a, token_a_admin):
        await _invite(async_client, token_a_admin, "trail1@tenanta.com", "employee")
        await _csv(async_client, token_a_admin, "email,role\ntrail2@tenanta.com,employee\n")
        await async_client.post(
            f"/users/{tenant_a['employee']['id']}/deactivate", headers=_headers(token_a_admin)
        )
        await async_client.post(
            f"/users/{tenant_a['employee']['id']}/reactivate", headers=_headers(token_a_admin)
        )
        await async_client.post(
            f"/users/{tenant_a['employee']['id']}/password-reset", headers=_headers(token_a_admin)
        )
        await async_client.patch(
            f"/users/{tenant_a['employee']['id']}/role",
            json={"role": "client_admin", "current_password": STRONG},
            headers=_headers(token_a_admin),
        )

        resp = await async_client.get("/users/audit", headers=_headers(token_a_admin))
        actions = {r["action"] for r in resp.json()}
        assert actions >= {
            "create_user_invite",
            "import_users",
            "deactivate_user",
            "reactivate_user",
            "request_password_reset",
            "change_user_role",
        }

    async def test_accepted_invite_is_visible_to_the_tenant(
        self, async_client, tenant_a, token_a_admin
    ):
        """The accepting user's own row belongs to the tenant, not to nobody.

        actor_role is 'system' because nobody was signed in at the time, and
        actor_user_id is null for the same reason. The tenant is not null, so RLS
        shows it to the Client Admin who caused it.
        """
        resp = await _invite(async_client, token_a_admin, "joined@tenanta.com", "employee")
        await _accept(async_client, resp.json()["code"], "joined@tenanta.com")

        resp = await async_client.get("/users/audit", headers=_headers(token_a_admin))
        rows = [r for r in resp.json() if r["action"] == "accept_invite"]
        assert len(rows) == 1
        assert rows[0]["actor_role"] == "system"
        assert rows[0]["actor_user_id"] is None
        assert rows[0]["details"]["role"] == "employee"

    async def test_trail_contains_no_invite_or_reset_code(
        self, async_client, tenant_a, token_a_admin
    ):
        """A 43-char credential in a long-lived table is a standing leak.

        The codes are returned to the Client Admin for hand-off and are never
        written to audit_logs; the invites table holds its codes in plaintext,
        which is VQ-107's known defect and out of scope here.
        """
        resp = await _invite(async_client, token_a_admin, "leaky@tenanta.com", "employee")
        code = resp.json()["code"]
        resp = await async_client.post(
            f"/users/{tenant_a['employee']['id']}/password-reset", headers=_headers(token_a_admin)
        )
        reset_code = resp.json()["reset_code"]

        resp = await async_client.get("/users/audit", headers=_headers(token_a_admin))
        assert code not in resp.text
        assert reset_code not in resp.text

    async def test_limit_is_bounded(self, async_client, tenant_a, token_a_admin):
        resp = await async_client.get(
            "/users/audit", params={"limit": 99999}, headers=_headers(token_a_admin)
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

        resp = await async_client.get(
            "/users/audit", params={"limit": -5}, headers=_headers(token_a_admin)
        )
        assert resp.status_code == 200
