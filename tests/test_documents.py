import pytest
import pytest_asyncio
import uuid
import httpx
import io
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
        (str(tenant_a), "usera@tenant_a.com", hash_password("StrongPass1!"), "client_admin"),
    )
    user_id = cur.fetchone()[0]
    db_conn.commit()
    return user_id


@pytest.fixture
def user_b(db_conn, tenant_b):
    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO users (tenant_id, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
        (str(tenant_b), "userb@tenant_b.com", hash_password("StrongPass1!"), "client_admin"),
    )
    user_id = cur.fetchone()[0]
    db_conn.commit()
    return user_id


@pytest.fixture
def tenant_a_token(client: httpx.AsyncClient, tenant_a, user_a):
    async def _get_token():
        response = await client.post(
            "/auth/login",
            json={
                "organisation_code": "TENANT_A",
                "email": "usera@tenant_a.com",
                "password": "StrongPass1!",
            },
        )
        return response.json()["access_token"]
    return _get_token


@pytest.fixture
def tenant_b_token(client: httpx.AsyncClient, tenant_b, user_b):
    async def _get_token():
        response = await client.post(
            "/auth/login",
            json={
                "organisation_code": "TENANT_B",
                "email": "userb@tenant_b.com",
                "password": "StrongPass1!",
            },
        )
        return response.json()["access_token"]
    return _get_token


class TestDocumentUpload:
    @pytest.mark.asyncio
    async def test_upload_document_success(self, client: httpx.AsyncClient, tenant_a_token):
        token = await tenant_a_token()
        file_content = b"This is a test document content"
        files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}

        response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["original_filename"] == "test.txt"
        assert data["mime_type"] == "text/plain"
        assert data["size_bytes"] == len(file_content)
        assert "id" in data
        assert "stored_filename" in data

    @pytest.mark.asyncio
    async def test_upload_rejects_disallowed_mime_type(self, client: httpx.AsyncClient, tenant_a_token):
        token = await tenant_a_token()
        file_content = b"<?php echo 'evil'; ?>"
        files = {"file": ("evil.php", io.BytesIO(file_content), "application/x-php")}

        response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
        )
        assert response.status_code == 415

    @pytest.mark.asyncio
    async def test_upload_rejects_large_file(self, client: httpx.AsyncClient, tenant_a_token):
        token = await tenant_a_token()
        large_content = b"x" * (60 * 1024 * 1024)  # 60MB
        files = {"file": ("large.txt", io.BytesIO(large_content), "text/plain")}

        response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
        )
        assert response.status_code == 413

    @pytest.mark.asyncio
    async def test_upload_filename_not_in_path(self, client: httpx.AsyncClient, tenant_a_token, db_conn):
        token = await tenant_a_token()
        file_content = b"test"
        files = {"file": ("../../etc/passwd", io.BytesIO(file_content), "text/plain")}

        response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
        )
        assert response.status_code == 201

        # Verify stored filename is UUID-based, not the user-provided filename
        data = response.json()
        stored_filename = data["stored_filename"]
        assert "../../etc/passwd" not in stored_filename
        assert "passwd" not in stored_filename


class TestDocumentList:
    @pytest.mark.asyncio
    async def test_list_documents(self, client: httpx.AsyncClient, tenant_a_token, tenant_a, user_a):
        token = await tenant_a_token()

        # Upload a document first
        files = {"file": ("doc1.txt", io.BytesIO(b"content1"), "text/plain")}
        await client.post("/documents", headers={"Authorization": f"Bearer {token}"}, files=files)

        # List documents
        response = await client.get(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["documents"]) >= 1
        assert data["page"] == 1
        assert data["page_size"] == 20


class TestDocumentPreview:
    @pytest.mark.asyncio
    async def test_preview_text_document(self, client: httpx.AsyncClient, tenant_a_token):
        token = await tenant_a_token()
        content = "This is a test document for preview. " * 100
        files = {"file": ("preview.txt", io.BytesIO(content.encode()), "text/plain")}

        upload_response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
        )
        doc_id = upload_response.json()["id"]

        response = await client.get(
            f"/documents/{doc_id}/preview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "preview" in data
        assert data["truncated"] is True or len(data["preview"]) <= 5000


class TestDocumentDownload:
    @pytest.mark.asyncio
    async def test_download_document(self, client: httpx.AsyncClient, tenant_a_token):
        token = await tenant_a_token()
        content = b"Download test content"
        files = {"file": ("download.txt", io.BytesIO(content), "text/plain")}

        upload_response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
        )
        doc_id = upload_response.json()["id"]

        response = await client.get(
            f"/documents/{doc_id}/download",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.content == content
        assert "download.txt" in response.headers.get("content-disposition", "")


class TestCrossTenantAccess:
    @pytest.mark.asyncio
    async def test_cross_tenant_download_returns_404(
        self, client: httpx.AsyncClient, tenant_a_token, tenant_b_token, tenant_a, tenant_b, user_a
    ):
        token_a = await tenant_a_token()
        token_b = await tenant_b_token()

        # Tenant A uploads a document
        files = {"file": ("secret.txt", io.BytesIO(b"Tenant A secret"), "text/plain")}
        upload_response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token_a}"},
            files=files,
        )
        doc_id = upload_response.json()["id"]

        # Tenant B tries to download it
        response = await client.get(
            f"/documents/{doc_id}/download",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cross_tenant_preview_returns_404(
        self, client: httpx.AsyncClient, tenant_a_token, tenant_b_token
    ):
        token_a = await tenant_a_token()
        token_b = await tenant_b_token()

        files = {"file": ("secret.txt", io.BytesIO(b"Tenant A secret"), "text/plain")}
        upload_response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token_a}"},
            files=files,
        )
        doc_id = upload_response.json()["id"]

        response = await client.get(
            f"/documents/{doc_id}/preview",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cross_tenant_delete_returns_404(
        self, client: httpx.AsyncClient, tenant_a_token, tenant_b_token
    ):
        token_a = await tenant_a_token()
        token_b = await tenant_b_token()

        files = {"file": ("secret.txt", io.BytesIO(b"Tenant A secret"), "text/plain")}
        upload_response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token_a}"},
            files=files,
        )
        doc_id = upload_response.json()["id"]

        response = await client.delete(
            f"/documents/{doc_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert response.status_code == 404


class TestDocumentDelete:
    @pytest.mark.asyncio
    async def test_delete_document(self, client: httpx.AsyncClient, tenant_a_token):
        token = await tenant_a_token()
        files = {"file": ("todelete.txt", io.BytesIO(b"delete me"), "text/plain")}

        upload_response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
        )
        doc_id = upload_response.json()["id"]

        # Delete the document
        response = await client.delete(
            f"/documents/{doc_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 204

        # Verify it's gone
        response = await client.get(
            f"/documents/{doc_id}/download",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


class TestBulkUpload:
    @pytest.mark.asyncio
    async def test_bulk_upload_multiple_files(self, client: httpx.AsyncClient, tenant_a_token):
        token = await tenant_a_token()
        files = [
            ("files", ("one.txt", io.BytesIO(b"First bulk file"), "text/plain")),
            ("files", ("two.md", io.BytesIO(b"# Second bulk file"), "text/markdown")),
            ("files", ("three.csv", io.BytesIO(b"a,b,c\n1,2,3"), "text/csv")),
        ]

        response = await client.post(
            "/documents/bulk",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["processed"] == 3
        assert data["created"] == 3
        assert data["failed"] == 0
        assert len(data["results"]) == 3
        assert all(r["success"] is True for r in data["results"])
        assert {r["filename"] for r in data["results"]} == {"one.txt", "two.md", "three.csv"}
        assert all(r["document"]["tenant_id"] for r in data["results"])

    @pytest.mark.asyncio
    async def test_bulk_upload_single_file(self, client: httpx.AsyncClient, tenant_a_token):
        token = await tenant_a_token()
        files = [("files", ("solo.txt", io.BytesIO(b"only one"), "text/plain"))]

        response = await client.post(
            "/documents/bulk",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["processed"] == 1
        assert data["created"] == 1
        assert data["failed"] == 0

    @pytest.mark.asyncio
    async def test_bulk_upload_partial_failure(self, client: httpx.AsyncClient, tenant_a_token):
        token = await tenant_a_token()
        files = [
            ("files", ("good.txt", io.BytesIO(b"valid content"), "text/plain")),
            ("files", ("evil.php", io.BytesIO(b"<?php echo 'x'; ?>"), "application/x-php")),
            ("files", ("good2.txt", io.BytesIO(b"another valid"), "text/plain")),
        ]

        response = await client.post(
            "/documents/bulk",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["processed"] == 3
        assert data["created"] == 2
        assert data["failed"] == 1

        by_name = {r["filename"]: r for r in data["results"]}
        assert by_name["good.txt"]["success"] is True
        assert by_name["good2.txt"]["success"] is True
        assert by_name["evil.php"]["success"] is False
        assert by_name["evil.php"]["error"] is not None

    @pytest.mark.asyncio
    async def test_bulk_upload_rejects_empty_batch(self, client: httpx.AsyncClient, tenant_a_token):
        token = await tenant_a_token()
        response = await client.post(
            "/documents/bulk",
            headers={"Authorization": f"Bearer {token}"},
            files=[],
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_bulk_upload_rejects_too_many_files(self, client: httpx.AsyncClient, tenant_a_token):
        token = await tenant_a_token()
        files = [
            ("files", (f"f{i}.txt", io.BytesIO(b"x"), "text/plain"))
            for i in range(11)
        ]
        response = await client.post(
            "/documents/bulk",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_bulk_upload_requires_auth(self, client: httpx.AsyncClient):
        files = [("files", ("nope.txt", io.BytesIO(b"x"), "text/plain"))]
        response = await client.post("/documents/bulk", files=files)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_bulk_upload_cross_tenant_isolation(
        self, client: httpx.AsyncClient, tenant_a_token, tenant_b_token
    ):
        token_a = await tenant_a_token()
        token_b = await tenant_b_token()

        files = [
            ("files", ("a.txt", io.BytesIO(b"tenant A"), "text/plain")),
            ("files", ("b.txt", io.BytesIO(b"tenant A also"), "text/plain")),
        ]
        response = await client.post(
            "/documents/bulk",
            headers={"Authorization": f"Bearer {token_a}"},
            files=files,
        )
        doc_ids = [r["document"]["id"] for r in response.json()["results"]]

        for doc_id in doc_ids:
            resp = await client.get(
                f"/documents/{doc_id}/download",
                headers={"Authorization": f"Bearer {token_b}"},
            )
            assert resp.status_code == 404


class TestStorageUsage:
    @pytest.mark.asyncio
    async def test_storage_usage(self, client: httpx.AsyncClient, tenant_a_token):
        token = await tenant_a_token()

        # Upload multiple documents
        for i in range(3):
            content = f"Document {i} content".encode()
            files = {"file": (f"doc{i}.txt", io.BytesIO(content), "text/plain")}
            await client.post(
                "/documents",
                headers={"Authorization": f"Bearer {token}"},
                files=files,
            )

        response = await client.get(
            "/documents/usage",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_documents"] >= 3
        assert data["total_size_bytes"] > 0
        assert data["total_size_mb"] >= 0


class TestPathTraversal:
    @pytest.mark.asyncio
    async def test_filename_path_traversal_attempts(
        self, client: httpx.AsyncClient, tenant_a_token, db_conn
    ):
        token = await tenant_a_token()

        # Various path traversal attempts
        malicious_filenames = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "/etc/passwd",
            "C:\\Windows\\System32\\config\\SAM",
            "normal.txt/../../../etc/passwd",
        ]

        for filename in malicious_filenames:
            files = {"file": (filename, io.BytesIO(b"test"), "text/plain")}
            response = await client.post(
                "/documents",
                headers={"Authorization": f"Bearer {token}"},
                files=files,
            )
            assert response.status_code == 201
            data = response.json()
            stored = data["stored_filename"]
            assert ".." not in stored
            assert "/" not in stored
            assert "\\" not in stored