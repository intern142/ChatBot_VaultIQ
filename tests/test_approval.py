"""VQ-202: approval workflow and document versions.

The load-bearing tests here are TestApprovalSwap and TestSingleApprovedInvariant.
AC3 asks for "no moment where both or neither are searchable", so the tests assert
the invariant holds at rest and that the database refuses to break it, not merely
that the happy path returns 200.
"""

import uuid

import pytest
from httpx import AsyncClient


@pytest.fixture
def client(async_client):
    return async_client


@pytest.fixture
def client_admin_a_headers(token_a_admin):
    return {"Authorization": f"Bearer {token_a_admin}"}


@pytest.fixture
def employee_a_headers(token_a_emp):
    return {"Authorization": f"Bearer {token_a_emp}"}


@pytest.fixture
def client_admin_b_headers(token_b_admin):
    return {"Authorization": f"Bearer {token_b_admin}"}


def _file(name="policy.txt", body=b"Leave requests must be approved by a manager."):
    return {"file": (name, body, "text/plain")}


async def _upload(client, headers, name="policy.txt", replaces=None, body=b"content"):
    files = {"file": (name, body, "text/plain")}
    # `replaces` is a form field, not a file part. Putting it in `files` makes
    # httpx send it as a file with a filename, which FastAPI rejects with 422.
    data = {"replaces": replaces} if replaces else None
    r = await client.post("/documents", files=files, data=data, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


async def _approve(client, headers, document_id, note=None):
    body = {"note": note} if note is not None else {}
    return await client.post(
        f"/documents/{document_id}/approve", json=body, headers=headers
    )


class TestStateMachine:
    """AC1: Pending -> Approved -> Archived. Only approved takes part in search."""

    @pytest.mark.asyncio
    async def test_new_document_is_born_pending(self, client, client_admin_a_headers):
        doc = await _upload(client, client_admin_a_headers)
        assert doc["status"] == "pending"
        assert doc["version_number"] == 1

    @pytest.mark.asyncio
    async def test_approve_moves_to_approved(self, client, client_admin_a_headers):
        doc = await _upload(client, client_admin_a_headers)
        r = await _approve(client, client_admin_a_headers, doc["id"])
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "approved"
        assert r.json()["approved_at"] is not None
        assert r.json()["approved_by"] is not None

    @pytest.mark.asyncio
    async def test_reject_moves_to_rejected(self, client, client_admin_a_headers):
        doc = await _upload(client, client_admin_a_headers)
        r = await client.post(
            f"/documents/{doc['id']}/reject", json={"note": "wrong policy"},
            headers=client_admin_a_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "rejected"
        assert r.json()["decision_note"] == "wrong policy"

    @pytest.mark.asyncio
    async def test_pending_document_never_searchable(
        self, client, client_admin_a_headers
    ):
        """AC1: a Pending document never appears in results."""
        doc = await _upload(client, client_admin_a_headers)
        r = await client.get("/documents/searchable/approved", headers=client_admin_a_headers)
        assert r.status_code == 200
        ids = {d["id"] for d in r.json()["documents"]}
        assert doc["id"] not in ids

    @pytest.mark.asyncio
    async def test_rejected_document_never_searchable(
        self, client, client_admin_a_headers
    ):
        doc = await _upload(client, client_admin_a_headers)
        await client.post(
            f"/documents/{doc['id']}/reject", json={}, headers=client_admin_a_headers
        )
        r = await client.get("/documents/searchable/approved", headers=client_admin_a_headers)
        ids = {d["id"] for d in r.json()["documents"]}
        assert doc["id"] not in ids

    @pytest.mark.asyncio
    async def test_approved_document_is_searchable(
        self, client, client_admin_a_headers
    ):
        doc = await _upload(client, client_admin_a_headers)
        await _approve(client, client_admin_a_headers, doc["id"])
        r = await client.get("/documents/searchable/approved", headers=client_admin_a_headers)
        ids = {d["id"] for d in r.json()["documents"]}
        assert doc["id"] in ids


class TestIllegalTransitions:
    @pytest.mark.asyncio
    async def test_cannot_approve_twice(self, client, client_admin_a_headers):
        doc = await _upload(client, client_admin_a_headers)
        await _approve(client, client_admin_a_headers, doc["id"])
        r = await _approve(client, client_admin_a_headers, doc["id"])
        assert r.status_code == 409
        assert "only 'pending' can be approved" in r.json()["detail"]

    @pytest.mark.asyncio
    async def test_cannot_reject_an_approved_document(
        self, client, client_admin_a_headers
    ):
        doc = await _upload(client, client_admin_a_headers)
        await _approve(client, client_admin_a_headers, doc["id"])
        r = await client.post(
            f"/documents/{doc['id']}/reject", json={}, headers=client_admin_a_headers
        )
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_cannot_approve_a_rejected_document(
        self, client, client_admin_a_headers
    ):
        """rejected is terminal."""
        doc = await _upload(client, client_admin_a_headers)
        await client.post(
            f"/documents/{doc['id']}/reject", json={}, headers=client_admin_a_headers
        )
        r = await _approve(client, client_admin_a_headers, doc["id"])
        assert r.status_code == 409


class TestApprovalSwap:
    """AC3: approving v2 retires v1, atomically, with no gap and no overlap."""

    @pytest.mark.asyncio
    async def test_new_version_joins_the_group_as_pending(
        self, client, client_admin_a_headers
    ):
        v1 = await _upload(client, client_admin_a_headers, "policy.txt")
        await _approve(client, client_admin_a_headers, v1["id"])

        v2 = await _upload(
            client, client_admin_a_headers, "policy.txt", replaces=v1["id"]
        )

        assert v2["document_group_id"] == v1["document_group_id"]
        assert v2["version_number"] == 2
        assert v2["supersedes_id"] == v1["id"]
        assert v2["status"] == "pending"

    @pytest.mark.asyncio
    async def test_approving_v2_retires_v1(self, client, client_admin_a_headers):
        v1 = await _upload(client, client_admin_a_headers, "policy.txt")
        await _approve(client, client_admin_a_headers, v1["id"])
        v2 = await _upload(client, client_admin_a_headers, "policy.txt", replaces=v1["id"])

        r = await _approve(client, client_admin_a_headers, v2["id"])
        assert r.status_code == 200, r.text

        r = await client.get(
            f"/documents/{v1['id']}/versions", headers=client_admin_a_headers
        )
        assert r.status_code == 200
        by_id = {d["id"]: d for d in r.json()["versions"]}
        assert by_id[v1["id"]]["status"] == "archived"
        assert by_id[v2["id"]]["status"] == "approved"

    @pytest.mark.asyncio
    async def test_exactly_one_approved_at_every_point(
        self, client, client_admin_a_headers
    ):
        """The core of AC3. After every step the group holds exactly one approved."""
        async def approved_ids():
            r = await client.get(
                "/documents/searchable/approved", headers=client_admin_a_headers
            )
            return {d["id"] for d in r.json()["documents"]}

        v1 = await _upload(client, client_admin_a_headers, "policy.txt")
        assert await approved_ids() == set()

        await _approve(client, client_admin_a_headers, v1["id"])
        assert await approved_ids() == {v1["id"]}

        v2 = await _upload(client, client_admin_a_headers, "policy.txt", replaces=v1["id"])
        # v2 exists but is pending: still exactly v1, never neither, never both.
        assert await approved_ids() == {v1["id"]}

        await _approve(client, client_admin_a_headers, v2["id"])
        assert await approved_ids() == {v2["id"]}

    @pytest.mark.asyncio
    async def test_version_history_is_ordered(self, client, client_admin_a_headers):
        v1 = await _upload(client, client_admin_a_headers, "policy.txt")
        await _approve(client, client_admin_a_headers, v1["id"])
        v2 = await _upload(client, client_admin_a_headers, "policy.txt", replaces=v1["id"])
        await _approve(client, client_admin_a_headers, v2["id"])
        v3 = await _upload(client, client_admin_a_headers, "policy.txt", replaces=v2["id"])

        r = await client.get(
            f"/documents/{v1['id']}/versions", headers=client_admin_a_headers
        )
        assert r.status_code == 200
        versions = r.json()["versions"]
        assert [v["version_number"] for v in versions] == [1, 2, 3]
        # v1 was retired when v2 was approved; v2 is the current approved version;
        # v3 is uploaded but not yet approved.
        assert [v["status"] for v in versions] == ["archived", "approved", "pending"]


class TestSingleApprovedInvariant:
    """The invariant is enforced by Postgres, not by application code."""

    @pytest.mark.asyncio
    async def test_database_refuses_two_approved_versions(self, db_conn):
        """Even a hand-written INSERT bypassing the app cannot break the invariant."""
        tid, uid = _seed_tenant_and_user(db_conn)
        group = str(uuid.uuid4())

        _insert_version(db_conn, tid, uid, group, 1, "approved")
        with pytest.raises(Exception) as exc:
            _insert_version(db_conn, tid, uid, group, 2, "approved")
        assert "uq_documents_one_approved_per_group" in str(exc.value)
        conn_rollback(db_conn)

    @pytest.mark.asyncio
    async def test_two_pending_versions_are_fine(self, db_conn):
        """Only the approved state is constrained; queueing several is normal."""
        tid, uid = _seed_tenant_and_user(db_conn)
        group = str(uuid.uuid4())
        _insert_version(db_conn, tid, uid, group, 1, "pending")
        _insert_version(db_conn, tid, uid, group, 2, "pending")
        assert _approved_count(db_conn, group) == 0

    @pytest.mark.asyncio
    async def test_archived_and_approved_can_coexist(self, db_conn):
        tid, uid = _seed_tenant_and_user(db_conn)
        group = str(uuid.uuid4())
        _insert_version(db_conn, tid, uid, group, 1, "approved")
        _insert_version(db_conn, tid, uid, group, 2, "archived")
        assert _approved_count(db_conn, group) == 1


class TestKnowledgeBaseVersion:
    """AC5: the version moves when the approved set changes."""

    @pytest.mark.asyncio
    async def test_approve_bumps_it(self, client, client_admin_a_headers):
        before = (
            await client.get("/documents/searchable/approved", headers=client_admin_a_headers)
        ).json()["knowledge_base_version"]
        doc = await _upload(client, client_admin_a_headers)
        await _approve(client, client_admin_a_headers, doc["id"])
        after = (
            await client.get("/documents/searchable/approved", headers=client_admin_a_headers)
        ).json()["knowledge_base_version"]
        assert after == before + 1

    @pytest.mark.asyncio
    async def test_reject_does_not_bump_it(self, client, client_admin_a_headers):
        """The approved set did not change, so nothing should be invalidated."""
        before = (
            await client.get("/documents/searchable/approved", headers=client_admin_a_headers)
        ).json()["knowledge_base_version"]
        doc = await _upload(client, client_admin_a_headers)
        await client.post(
            f"/documents/{doc['id']}/reject", json={}, headers=client_admin_a_headers
        )
        after = (
            await client.get("/documents/searchable/approved", headers=client_admin_a_headers)
        ).json()["knowledge_base_version"]
        assert after == before

    @pytest.mark.asyncio
    async def test_swapping_versions_bumps_once_each(
        self, client, client_admin_a_headers
    ):
        v1 = await _upload(client, client_admin_a_headers, "policy.txt")
        await _approve(client, client_admin_a_headers, v1["id"])
        base = (
            await client.get("/documents/searchable/approved", headers=client_admin_a_headers)
        ).json()["knowledge_base_version"]
        v2 = await _upload(client, client_admin_a_headers, "policy.txt", replaces=v1["id"])
        await _approve(client, client_admin_a_headers, v2["id"])
        after = (
            await client.get("/documents/searchable/approved", headers=client_admin_a_headers)
        ).json()["knowledge_base_version"]
        assert after == base + 1


class TestPermissions:
    """AC2/the control: only a Client Admin may approve."""

    @pytest.mark.asyncio
    async def test_employee_cannot_approve(self, client, employee_a_headers):
        doc = await _upload(client, employee_a_headers)
        r = await _approve(client, employee_a_headers, doc["id"])
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_employee_cannot_reject(self, client, employee_a_headers):
        doc = await _upload(client, employee_a_headers)
        r = await client.post(
            f"/documents/{doc['id']}/reject", json={}, headers=employee_a_headers
        )
        assert r.status_code == 403

    @pytest.mark.asyncio
    async def test_employee_cannot_read_version_history(
        self, client, employee_a_headers
    ):
        doc = await _upload(client, employee_a_headers)
        r = await client.get(
            f"/documents/{doc['id']}/versions", headers=employee_a_headers
        )
        assert r.status_code == 403


class TestTenantIsolation:
    """A Client Admin of one tenant must not be able to touch another's document."""

    @pytest.mark.asyncio
    async def test_cannot_approve_another_tenants_document(
        self, client, client_admin_a_headers, client_admin_b_headers
    ):
        doc = await _upload(client, client_admin_a_headers)
        r = await _approve(client, client_admin_b_headers, doc["id"])
        assert r.status_code == 404
        assert r.json()["detail"] == "Document not found"

    @pytest.mark.asyncio
    async def test_cannot_read_another_tenants_version_history(
        self, client, client_admin_a_headers, client_admin_b_headers
    ):
        doc = await _upload(client, client_admin_a_headers)
        r = await client.get(
            f"/documents/{doc['id']}/versions", headers=client_admin_b_headers
        )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_searchable_list_never_crosses_tenants(
        self, client, client_admin_a_headers, client_admin_b_headers
    ):
        a_doc = await _upload(client, client_admin_a_headers, "a.txt")
        await _approve(client, client_admin_a_headers, a_doc["id"])
        b_doc = await _upload(client, client_admin_b_headers, "b.txt")
        await _approve(client, client_admin_b_headers, b_doc["id"])

        r = await client.get("/documents/searchable/approved", headers=client_admin_b_headers)
        ids = {d["id"] for d in r.json()["documents"]}
        assert ids == {b_doc["id"]}
        assert a_doc["id"] not in ids

    @pytest.mark.asyncio
    async def test_malformed_replaces_is_indistinguishable_from_missing(
        self, client, client_admin_a_headers
    ):
        """A junk id must not be a distinguishable probe for valid ids."""
        data = dict(_file("policy.txt"))
        junk = await client.post(
            "/documents",
            files={"file": ("policy.txt", b"x", "text/plain")},
            data={"replaces": "not-a-uuid"},
            headers=client_admin_a_headers,
        )
        missing = await client.post(
            "/documents",
            files={"file": ("policy.txt", b"x", "text/plain")},
            data={"replaces": str(uuid.uuid4())},
            headers=client_admin_a_headers,
        )
        assert junk.status_code == missing.status_code == 404
        assert junk.json() == missing.json()


# --- helpers for the raw-SQL invariant tests -------------------------------


def _seed_tenant_and_user(conn):
    """Seed straight through the DDL identity.

    These tests assert what the database itself will and will not accept, so they
    must not go through the application - they bypass the tenant context entirely.
    UUIDs are passed as str because psycopg2 has no adapter registered for them.
    """
    code = ("INV" + uuid.uuid4().hex[:8]).upper()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO tenants (short_code, name, status) VALUES (%s, 'Inv', 'active') "
        "RETURNING id",
        (code,),
    )
    tid = cur.fetchone()[0]
    cur.execute(
        "INSERT INTO users (tenant_id, email, password_hash, role) "
        "VALUES (%s, %s, 'x', 'client_admin') RETURNING id",
        (str(tid), f"{code.lower()}@t.com"),
    )
    uid = cur.fetchone()[0]
    conn.commit()
    return tid, uid


def _insert_version(conn, tid, uid, group, number, status):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO documents (id, tenant_id, original_filename, stored_filename, "
        "mime_type, size_bytes, uploaded_by, document_group_id, version_number, status) "
        "VALUES (%s, %s, 'f.txt', 'f.txt', 'text/plain', 1, %s, %s, %s, %s)",
        (str(uuid.uuid4()), str(tid), str(uid), str(group), number, status),
    )
    conn.commit()
    return group


def conn_rollback(conn):
    """Clear the aborted transaction so the connection stays usable."""
    conn.rollback()


def _approved_count(conn, group):
    cur = conn.cursor()
    cur.execute(
        "SELECT count(*) FROM documents WHERE document_group_id = %s AND status = 'approved'",
        (str(group),),
    )
    return cur.fetchone()[0]
