import pytest
import pytest_asyncio
import uuid
import httpx
import io
from pathlib import Path
from app.main import app
from app.auth.password import hash_password
from app.auth.jwt import create_access_token
from app.schemas.tenant import TenantStatus
from app.config import get_settings


def make_minimal_pdf() -> bytes:
    stream = b"BT /F1 18 Tf 72 720 Td (VaultIQ test document) Tj ET"
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >> endobj\n",
        b"4 0 obj << /Length " + str(len(stream)).encode() + b" >> stream\n" + stream + b"\nendstream endobj\n",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n",
    ]
    document = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(document))
        document.extend(obj)
    xref_offset = len(document)
    document.extend(f"xref\n0 {len(offsets)}\n".encode())
    document.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        document.extend(f"{offset:010d} 00000 n \n".encode())
    document.extend(
        f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode()
    )
    return bytes(document)


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
def employee_a(db_conn, tenant_a):
    cur = db_conn.cursor()
    cur.execute(
        "INSERT INTO users (tenant_id, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
        (str(tenant_a), "employee_a@tenant_a.com", hash_password("StrongPass1!"), "employee"),
    )
    user_id = cur.fetchone()[0]
    db_conn.commit()
    return user_id


@pytest.fixture
def employee_a_token(client: httpx.AsyncClient, tenant_a, employee_a):
    async def _get_token():
        response = await client.post(
            "/auth/login",
            json={
                "organisation_code": "TENANT_A",
                "email": "employee_a@tenant_a.com",
                "password": "StrongPass1!",
            },
        )
        return response.json()["access_token"]
    return _get_token


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
        data = {"category": "policy"}

        response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
        )
        assert response.status_code == 201
        resp_data = response.json()
        assert resp_data["original_filename"] == "test.txt"
        assert resp_data["mime_type"] == "text/plain"
        assert resp_data["size_bytes"] == len(file_content)
        assert "id" in resp_data
        assert "stored_filename" in resp_data
        assert resp_data["category"] == "policy"
        assert resp_data["extraction_status"] == "not_required"
        assert resp_data["extraction_method"] == "none"

    @pytest.mark.asyncio
    async def test_upload_persists_extraction_metadata(
        self, client: httpx.AsyncClient, tenant_a_token, monkeypatch
    ):
        from app.services.ocr import ExtractionResult

        def extraction_result(path, mime_type):
            return ExtractionResult("Extracted customer text", "ocr", "completed", 1, False)

        monkeypatch.setattr(
            "app.routes.documents.extract_document_text",
            extraction_result,
        )
        token = await tenant_a_token()
        files = {"file": ("scan.pdf", io.BytesIO(make_minimal_pdf()), "application/pdf")}
        response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data={"category": "other"},
        )
        assert response.status_code == 201
        document = response.json()
        assert document["extraction_method"] == "ocr"
        assert document["extraction_status"] == "completed"
        assert document["extraction_page_count"] == 1
        assert document["extraction_truncated"] is False
        preview = await client.get(
            f"/documents/{document['id']}/preview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert preview.status_code == 200
        assert preview.json()["preview"] == "Extracted customer text"

    @pytest.mark.asyncio
    async def test_failed_extraction_removes_stored_file(
        self, client: httpx.AsyncClient, tenant_a_token, tenant_a, monkeypatch
    ):
        from app.config import get_settings
        from app.services.ocr import DocumentExtractionError

        def fail_extraction(path, mime_type):
            raise DocumentExtractionError("failed")

        monkeypatch.setattr("app.routes.documents.extract_document_text", fail_extraction)
        token = await tenant_a_token()
        files = {"file": ("document.pdf", io.BytesIO(make_minimal_pdf()), "application/pdf")}
        response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data={"category": "other"},
        )
        assert response.status_code == 422
        tenant_directory = Path(get_settings().STORAGE_ROOT) / str(tenant_a)
        assert not tenant_directory.exists() or not any(tenant_directory.iterdir())

    @pytest.mark.asyncio
    async def test_upload_rejects_disallowed_mime_type(self, client: httpx.AsyncClient, tenant_a_token):
        token = await tenant_a_token()
        file_content = b"<?php echo 'evil'; ?>"
        files = {"file": ("evil.php", io.BytesIO(file_content), "application/x-php")}
        data = {"category": "policy"}

        response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
        )
        assert response.status_code == 415

    @pytest.mark.asyncio
    async def test_upload_rejects_large_file(self, client: httpx.AsyncClient, tenant_a_token):
        token = await tenant_a_token()
        large_content = b"x" * (60 * 1024 * 1024)  # 60MB
        files = {"file": ("large.txt", io.BytesIO(large_content), "text/plain")}
        data = {"category": "policy"}

        response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
        )
        assert response.status_code == 413

    @pytest.mark.asyncio
    async def test_upload_filename_not_in_path(self, client: httpx.AsyncClient, tenant_a_token, db_conn):
        token = await tenant_a_token()
        file_content = b"test"
        files = {"file": ("../../etc/passwd", io.BytesIO(file_content), "text/plain")}
        data = {"category": "policy"}

        response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
        )
        assert response.status_code == 201

        # Verify stored filename is UUID-based, not the user-provided filename
        resp_data = response.json()
        stored_filename = resp_data["stored_filename"]
        assert "../../etc/passwd" not in stored_filename
        assert "passwd" not in stored_filename

    @pytest.mark.asyncio
    async def test_upload_rejects_missing_category(self, client: httpx.AsyncClient, tenant_a_token):
        token = await tenant_a_token()
        file_content = b"test"
        files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
        # No category provided

        response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
        )
        assert response.status_code == 422  # FastAPI validation error

    @pytest.mark.asyncio
    async def test_upload_rejects_invalid_category(self, client: httpx.AsyncClient, tenant_a_token):
        token = await tenant_a_token()
        file_content = b"test"
        files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
        data = {"category": "invalid_category"}

        response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_upload_employee_forbidden(self, client: httpx.AsyncClient, employee_a_token):
        token = await employee_a_token()
        file_content = b"test"
        files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
        data = {"category": "policy"}

        response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
        )
        assert response.status_code == 403


class TestDocumentList:
    @pytest.mark.asyncio
    async def test_list_documents(self, client: httpx.AsyncClient, tenant_a_token, tenant_a, user_a):
        token = await tenant_a_token()

        # Upload a document first
        files = {"file": ("doc1.txt", io.BytesIO(b"content1"), "text/plain")}
        data = {"category": "policy"}
        await client.post("/documents", headers={"Authorization": f"Bearer {token}"}, files=files, data=data)

        # List documents
        response = await client.get(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        resp_data = response.json()
        assert resp_data["total"] >= 1
        assert len(resp_data["documents"]) >= 1
        assert resp_data["page"] == 1
        assert resp_data["page_size"] == 20
        assert resp_data["documents"][0]["category"] == "policy"


class TestDocumentPreview:
    @pytest.mark.asyncio
    async def test_preview_text_document(self, client: httpx.AsyncClient, tenant_a_token):
        token = await tenant_a_token()
        content = "This is a test document for preview. " * 100
        files = {"file": ("preview.txt", io.BytesIO(content.encode()), "text/plain")}
        data = {"category": "policy"}

        upload_response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
        )
        doc_id = upload_response.json()["id"]

        response = await client.get(
            f"/documents/{doc_id}/preview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        resp_data = response.json()
        assert "preview" in resp_data
        assert resp_data["truncated"] is True or len(resp_data["preview"]) <= 5000


class TestDocumentDownload:
    @pytest.mark.asyncio
    async def test_download_document(self, client: httpx.AsyncClient, tenant_a_token):
        token = await tenant_a_token()
        content = b"Download test content"
        files = {"file": ("download.txt", io.BytesIO(content), "text/plain")}
        data = {"category": "policy"}

        upload_response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
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
        data = {"category": "policy"}
        upload_response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token_a}"},
            files=files,
            data=data,
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
        data = {"category": "policy"}
        upload_response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token_a}"},
            files=files,
            data=data,
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
        data = {"category": "policy"}
        upload_response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token_a}"},
            files=files,
            data=data,
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
        data = {"category": "policy"}

        upload_response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
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


class TestStorageUsage:
    @pytest.mark.asyncio
    async def test_storage_usage(self, client: httpx.AsyncClient, tenant_a_token):
        token = await tenant_a_token()

        # Upload multiple documents
        for i in range(3):
            content = f"Document {i} content".encode()
            files = {"file": (f"doc{i}.txt", io.BytesIO(content), "text/plain")}
            data = {"category": "policy"}
            await client.post(
                "/documents",
                headers={"Authorization": f"Bearer {token}"},
                files=files,
                data=data,
            )

        response = await client.get(
            "/documents/usage",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        resp_data = response.json()
        assert resp_data["total_documents"] >= 3
        assert resp_data["total_size_bytes"] > 0
        assert resp_data["total_size_mb"] >= 0


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
            data = {"category": "policy"}
            response = await client.post(
                "/documents",
                headers={"Authorization": f"Bearer {token}"},
                files=files,
                data=data,
            )
            assert response.status_code == 201
            resp_data = response.json()
            stored = resp_data["stored_filename"]
            assert ".." not in stored
            assert "/" not in stored
            assert "\\" not in stored


class TestQuotaEnforcement:
    @pytest.mark.asyncio
    async def test_quota_exceeded_rejects_upload(
        self, client: httpx.AsyncClient, tenant_a_token, tenant_a, db_conn
    ):
        """Test that upload is rejected when tenant quota would be exceeded."""
        token = await tenant_a_token()
        
        # Set tenant quota to very small (1KB)
        cur = db_conn.cursor()
        cur.execute("UPDATE tenants SET storage_quota_mb = 0.001 WHERE short_code = 'TENANT_A'")
        db_conn.commit()
        
        # Upload a file that exceeds quota
        file_content = b"x" * 2000  # 2KB
        files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
        data = {"category": "policy"}
        
        response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
        )
        assert response.status_code == 413
        assert "quota exceeded" in response.json()["detail"].lower()
        tenant_directory = Path(get_settings().STORAGE_ROOT) / str(tenant_a)
        assert not tenant_directory.exists()

    @pytest.mark.asyncio
    async def test_quota_allows_within_limit(self, client: httpx.AsyncClient, tenant_a_token, db_conn):
        """Test that upload succeeds when within quota."""
        token = await tenant_a_token()
        
        # Set tenant quota to 1MB
        cur = db_conn.cursor()
        cur.execute("UPDATE tenants SET storage_quota_mb = 1 WHERE short_code = 'TENANT_A'")
        db_conn.commit()
        
        # Upload a small file
        file_content = b"x" * 100  # 100 bytes
        files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
        data = {"category": "policy"}
        
        response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
        )
        assert response.status_code == 201


class TestContentBasedMimeDetection:
    @pytest.mark.asyncio
    async def test_mime_mismatch_rejected(self, client: httpx.AsyncClient, tenant_a_token):
        """Test that file with mismatched content vs header is rejected."""
        token = await tenant_a_token()
        
        # PHP content with .txt extension and text/plain content-type
        file_content = b"<?php echo 'evil'; ?>"
        files = {"file": ("evil.txt", io.BytesIO(file_content), "text/plain")}
        data = {"category": "policy"}
        
        response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
        )
        # Should be rejected because content is detected as application/x-php
        assert response.status_code == 415

    @pytest.mark.asyncio
    async def test_valid_pdf_accepted(self, client: httpx.AsyncClient, tenant_a_token):
        """Test that valid PDF content is accepted."""
        token = await tenant_a_token()
        
        # Minimal valid PDF content
        file_content = make_minimal_pdf()
        files = {"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")}
        data = {"category": "policy"}
        
        response = await client.post(
            "/documents",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
        )
        assert response.status_code == 201
        assert response.json()["mime_type"] == "application/pdf"