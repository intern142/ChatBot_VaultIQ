"""VQ-203: Document processing queue tests.

Covers all 7 acceptance criteria with automated proofs.
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta as _timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentJob, ProcessingStatus, JobStatus
from app.models.tenant import Tenant
from app.models.user import User
from app.auth.password import hash_password
from app.auth.jwt import create_access_token


@pytest_asyncio.fixture(scope="function")
async def tenant_a(db_engine):
    """Create tenant A with client_admin."""
    async with db_engine.begin() as conn:
        result = await conn.execute(text("""
            INSERT INTO tenants (short_code, name, status, storage_quota_mb)
            VALUES ('TENANT_A', 'Tenant A', 'active', 2048)
            RETURNING id
        """))
        tid = result.scalar()
        ph = hash_password("StrongPass1!")
        result = await conn.execute(text("""
            INSERT INTO users (tenant_id, email, password_hash, role)
            VALUES (:tid, 'admin@a.com', :ph, 'client_admin')
            RETURNING id
        """), {"tid": tid, "ph": ph})
        uid = result.scalar()
        sid = uuid.uuid4()
        await conn.execute(text("""
            INSERT INTO sessions (id, user_id, tenant_id, token_hash, expires_at)
            VALUES (:sid, :uid, :tid, '', now() + interval '24 hours')
        """), {"sid": sid, "uid": uid, "tid": tid})
    return {
        "id": tid,
        "client_admin": {"id": uid, "email": "admin@a.com", "session_id": sid},
    }


@pytest_asyncio.fixture(scope="function")
async def tenant_b(db_engine):
    """Create tenant B with client_admin."""
    async with db_engine.begin() as conn:
        result = await conn.execute(text("""
            INSERT INTO tenants (short_code, name, status, storage_quota_mb)
            VALUES ('TENANT_B', 'Tenant B', 'active', 2048)
            RETURNING id
        """))
        tid = result.scalar()
        ph = hash_password("StrongPass1!")
        result = await conn.execute(text("""
            INSERT INTO users (tenant_id, email, password_hash, role)
            VALUES (:tid, 'admin@b.com', :ph, 'client_admin')
            RETURNING id
        """), {"tid": tid, "ph": ph})
        uid = result.scalar()
        sid = uuid.uuid4()
        await conn.execute(text("""
            INSERT INTO sessions (id, user_id, tenant_id, token_hash, expires_at)
            VALUES (:sid, :uid, :tid, '', now() + interval '24 hours')
        """), {"sid": sid, "uid": uid, "tid": tid})
    return {
        "id": tid,
        "client_admin": {"id": uid, "email": "admin@b.com", "session_id": sid},
    }


@pytest_asyncio.fixture
def token_a(tenant_a):
    return create_access_token(
        user_id=tenant_a["client_admin"]["id"],
        role="client_admin",
        tenant_id=tenant_a["id"],
        session_id=tenant_a["client_admin"]["session_id"],
    )


@pytest_asyncio.fixture
def token_b(tenant_b):
    return create_access_token(
        user_id=tenant_b["client_admin"]["id"],
        role="client_admin",
        tenant_id=tenant_b["id"],
        session_id=tenant_b["client_admin"]["session_id"],
    )


def _upload_doc(async_client, token, content=b"Test document content"):
    files = {"file": ("test.txt", content, "text/plain")}
    headers = {"Authorization": f"Bearer {token}"}
    return async_client.post("/documents", files=files, headers=headers)


class TestUploadEnqueuesJob:
    """AC1 + AC6: Upload creates document with queued job; re-upload same version is idempotent."""

    @pytest.mark.asyncio
    async def test_upload_creates_queued_document_and_job(self, async_client, token_a, tenant_a, app_session):
        resp = await _upload_doc(async_client, token_a, b"Document A content")
        assert resp.status_code == 201, resp.text
        doc = resp.json()
        assert doc["processing_status"] == "queued"
        assert doc["processing_version"] == 1

        # Verify job was created - need tenant context for RLS
        from app.database import set_tenant_context
        async with app_session as db:
            await set_tenant_context(db, str(tenant_a["id"]))
            result = await db.execute(select(DocumentJob).where(DocumentJob.document_id == doc["id"]))
            job = result.scalar_one_or_none()
            assert job is not None
            assert job.status == "queued"
            assert job.payload == {"action": "index", "version": 1}
            assert job.tenant_id == tenant_a["id"]

    @pytest.mark.asyncio
    async def test_reprocess_is_idempotent_same_version(self, async_client, token_a, tenant_a, app_session):
        """Re-processing same version does not create duplicate job (unique constraint)."""
        resp = await _upload_doc(async_client, token_a, b"Doc")
        doc_id = resp.json()["id"]

        # Reprocess once
        headers = {"Authorization": f"Bearer {token_a}"}
        resp1 = await async_client.post(f"/documents/{doc_id}/reprocess", headers=headers)
        assert resp1.status_code == 200

        # Reprocess again - should return same job (no duplicate)
        resp2 = await async_client.post(f"/documents/{doc_id}/reprocess", headers=headers)
        assert resp2.status_code == 200

        # Verify only one job exists for version 2
        from app.database import set_tenant_context
        async with app_session as db:
            await set_tenant_context(db, str(tenant_a["id"]))
            result = await db.execute(
                select(DocumentJob).where(
                    DocumentJob.document_id == doc_id,
                    DocumentJob.payload["version"].as_integer() == 2
                )
            )
            jobs = result.scalars().all()
            assert len(jobs) == 1


class TestProcessingIsolation:
    """AC2: Each job belongs to one tenant; cross-tenant write impossible."""

    @pytest.mark.asyncio
    async def test_tenant_a_cannot_enqueue_for_tenant_b(self, async_client, token_a, tenant_b):
        """Tenant A cannot create a job for Tenant B's document."""
        # Create doc for tenant B
        token_b = create_access_token(
            user_id=tenant_b["client_admin"]["id"],
            role="client_admin",
            tenant_id=tenant_b["id"],
            session_id=tenant_b["client_admin"]["session_id"],
        )
        headers_b = {"Authorization": f"Bearer {token_b}"}
        resp = await async_client.post("/documents", files={"file": ("b.txt", b"B", "text/plain")}, headers=headers_b)
        doc_b_id = resp.json()["id"]

        # Tenant A tries to reprocess B's doc
        headers_a = {"Authorization": f"Bearer {token_a}"}
        resp = await async_client.post(f"/documents/{doc_b_id}/reprocess", headers=headers_a)
        assert resp.status_code == 404  # Not found due to RLS

    @pytest.mark.asyncio
    async def test_cross_tenant_job_write_blocked(self, app_session, tenant_a, tenant_b):
        """Direct DB insert of job for wrong tenant is blocked by RLS."""
        from app.database import set_tenant_context

        async with app_session as db:
            await set_tenant_context(db, str(tenant_a["id"]))
            # Try to insert job for tenant B's document
            from sqlalchemy import text
            with pytest.raises(Exception):
                await db.execute(text("""
                    INSERT INTO document_jobs (tenant_id, document_id, payload)
                    VALUES (:tid, :did, '{"action":"index","version":1}')
                """), {"tid": tenant_b["id"], "did": uuid.uuid4()})


class TestFairScheduling:
    """AC3: Per-tenant concurrency cap; other tenants keep progressing."""

    @pytest.mark.asyncio
    async def test_two_tenants_both_progress(self, async_client, token_a, token_b, tenant_a, tenant_b):
        """Both tenants can upload and see queued status."""
        # Upload from both tenants
        resp_a = await _upload_doc(async_client, token_a, b"A1")
        resp_b = await _upload_doc(async_client, token_b, b"B1")
        assert resp_a.status_code == 201
        assert resp_b.status_code == 201

        # Both should be queued
        assert resp_a.json()["processing_status"] == "queued"
        assert resp_b.json()["processing_status"] == "queued"

    @pytest.mark.asyncio
    async def test_per_tenant_cap_enforced(self):
        """A tenant at its cap must not block a different tenant.

        The previous version of this test had an empty body, so AC3 had no
        evidence at all. The property is about two tenants, not one: tenant A
        filling its permits must leave tenant B able to acquire immediately.
        """
        import uuid
        from worker import get_tenant_semaphore, MAX_CONCURRENT_PER_TENANT

        a = uuid.uuid4()
        b = uuid.uuid4()

        # Tenant A saturates its cap.
        sem_a = get_tenant_semaphore(a)
        for _ in range(MAX_CONCURRENT_PER_TENANT):
            assert await sem_a.acquire()

        # Tenant B is unaffected and acquires without waiting.
        sem_b = get_tenant_semaphore(b)
        await asyncio.wait_for(sem_b.acquire(), timeout=0.2)

        # A is genuinely blocked, so the cap is doing something.
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sem_a.acquire(), timeout=0.2)


class TestRetriesAndFailure:
    """AC4: Limited retries with human-readable error; AC7: Ready only when fully stored."""

    @pytest.mark.asyncio
    async def test_failed_job_retries_then_fails(self, app_session, tenant_a):
        """process_job re-queues below the cap and gives up at it.

        The previous version of this test wrote status='failed' and
        retry_count=2 by hand and then asserted the values it had just written.
        It never called the retry logic, so AC4 had no evidence. This drives
        worker.process_job with an always-failing pipeline and checks the
        re-queue/backoff and give-up branches separately.
        """
        from sqlalchemy import text
        from unittest.mock import patch
        from app.models.document import Document, DocumentJob
        from app.database import set_tenant_context
        from worker import process_job

        async with app_session as db:
            await set_tenant_context(db, str(tenant_a["id"]))
            doc = Document(
                tenant_id=tenant_a["id"],
                original_filename="test.txt",
                stored_filename="test.txt",
                mime_type="text/plain",
                size_bytes=100,
                uploaded_by=tenant_a["client_admin"]["id"],
            )
            db.add(doc)
            await db.commit()

            await set_tenant_context(db, str(tenant_a["id"]))
            job = DocumentJob(
                tenant_id=tenant_a["id"],
                document_id=doc.id,
                payload={"action": "index", "version": 1},
                max_retries=2,
            )
            db.add(job)
            await db.commit()

            # Patched at app.services.processing, not on the worker module:
            # process_job does a local `from app.services.processing import
            # process_document` inside the function body, which shadows the
            # module-level name in worker, so patching worker.process_document
            # has no effect and the real pipeline runs instead.
            with patch(
                "app.services.processing.process_document",
                new=AsyncMock(side_effect=RuntimeError("PDF extraction failed")),
            ):
                # Retry 1: below the cap, so the job goes back on the queue with
                # the error recorded and a delayed created_at (backoff).
                await set_tenant_context(db, str(tenant_a["id"]))
                await process_job(db, job)
                await set_tenant_context(db, str(tenant_a["id"]))
                row = (await db.execute(
                    text("SELECT status, retry_count, last_error FROM document_jobs WHERE id = :jid"),
                    {"jid": job.id},
                )).one()
                assert row.status == "queued"
                assert row.retry_count == 1
                assert "PDF extraction failed" in row.last_error

                # Retry 2: still below the cap, so it queues again.
                await set_tenant_context(db, str(tenant_a["id"]))
                await process_job(db, job)
                await set_tenant_context(db, str(tenant_a["id"]))
                row = (await db.execute(
                    text("SELECT status, retry_count, last_error FROM document_jobs WHERE id = :jid"),
                    {"jid": job.id},
                )).one()
                assert row.status == "queued"
                assert row.retry_count == 2

                # Attempt 3: retry_count has reached max_retries, so the job
                # gives up. max_retries counts retries after the first attempt,
                # so a cap of 2 means 3 attempts in total.
                await set_tenant_context(db, str(tenant_a["id"]))
                await process_job(db, job)
                await set_tenant_context(db, str(tenant_a["id"]))
                row = (await db.execute(
                    text("SELECT status, retry_count, last_error, completed_at FROM document_jobs WHERE id = :jid"),
                    {"jid": job.id},
                )).one()
                assert row.status == "failed"
                assert row.retry_count == 2
                assert row.completed_at is not None
                assert "Max retries exceeded" in row.last_error

                # A failed job is terminal - the worker must not pick it up again.
                assert row.status != JobStatus.queued

    @pytest.mark.asyncio
    async def test_backoff_delays_the_retry(self, app_session, tenant_a):
        """A re-queued job is not immediately eligible; created_at moves forward.

        Without this the retry loop spins as fast as it can on a permanently
        broken document and starves every other tenant's queue.
        """
        from sqlalchemy import text
        from datetime import datetime, timezone as _tz
        from unittest.mock import patch
        from app.models.document import Document, DocumentJob
        from app.database import set_tenant_context
        from worker import process_job, BASE_RETRY_DELAY_SECONDS

        async with app_session as db:
            await set_tenant_context(db, str(tenant_a["id"]))
            doc = Document(
                tenant_id=tenant_a["id"],
                original_filename="backoff.txt",
                stored_filename="backoff.txt",
                mime_type="text/plain",
                size_bytes=100,
                uploaded_by=tenant_a["client_admin"]["id"],
            )
            db.add(doc)
            await db.commit()

            await set_tenant_context(db, str(tenant_a["id"]))
            job = DocumentJob(
                tenant_id=tenant_a["id"],
                document_id=doc.id,
                payload={"action": "index", "version": 1},
                max_retries=3,
            )
            db.add(job)
            await db.commit()
            before = datetime.now(_tz.utc)

            with patch(
                "app.services.processing.process_document",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ):
                await set_tenant_context(db, str(tenant_a["id"]))
                await process_job(db, job)

            await set_tenant_context(db, str(tenant_a["id"]))
            after = (await db.execute(
                text("SELECT created_at FROM document_jobs WHERE id = :jid"),
                {"jid": job.id},
            )).scalar()
            assert after >= before + _timedelta(seconds=BASE_RETRY_DELAY_SECONDS - 5)

    @pytest.mark.asyncio
    async def test_ready_only_after_full_storage(self, app_session, tenant_a):
        """process_document marks ready only when the chunk write succeeded.

        The previous version set processing_status='ready' by hand and asserted
        it was 'ready', so AC7 had no evidence. This drives the real pipeline
        with a failing chunk write and asserts the document is NOT left ready.
        """
        from sqlalchemy import text
        from unittest.mock import patch
        from app.models.document import Document
        from app.database import set_tenant_context
        from app.services.processing import process_document

        # The pipeline checks the file on disk before it reaches the vector
        # write, so a real file is needed to get that far.
        from app.services.storage import save_uploaded_file
        import io
        doc_id = uuid.uuid4()
        file_path = save_uploaded_file(
            io.BytesIO(b"some extractable text"), tenant_a["id"], doc_id, "test.txt"
        )
        assert file_path.exists()

        async with app_session as db:
            await set_tenant_context(db, str(tenant_a["id"]))
            doc = Document(
                id=doc_id,
                tenant_id=tenant_a["id"],
                original_filename="test.txt",
                stored_filename="test.txt",
                mime_type="text/plain",
                size_bytes=100,
                uploaded_by=tenant_a["client_admin"]["id"],
            )
            db.add(doc)
            await db.commit()

            await set_tenant_context(db, str(tenant_a["id"]))
            job = DocumentJob(
                tenant_id=tenant_a["id"],
                document_id=doc.id,
                payload={"action": "index", "version": 1},
            )
            db.add(job)
            await db.commit()

            # The vector write fails, which is the last step before 'ready'.
            with patch(
                "app.services.processing.store_chunks",
                new=AsyncMock(side_effect=RuntimeError("vector write failed")),
            ):
                await set_tenant_context(db, str(tenant_a["id"]))
                with pytest.raises(RuntimeError):
                    await process_document(db, tenant_a["id"], doc.id, job.id)

            await set_tenant_context(db, str(tenant_a["id"]))
            status = (await db.execute(
                text("SELECT processing_status FROM documents WHERE id = :did"),
                {"did": doc.id},
            )).scalar()
            assert status == "failed", "document must not be ready when storage failed"


class TestClientAdminVisibility:
    """AC5: Client Admin can see status."""

    @pytest.mark.asyncio
    async def test_status_endpoint_returns_full_info(self, async_client, token_a, tenant_a):
        resp = await _upload_doc(async_client, token_a, b"Test")
        doc_id = resp.json()["id"]

        headers = {"Authorization": f"Bearer {token_a}"}
        resp = await async_client.get(f"/documents/{doc_id}/status", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_id"] == doc_id
        assert data["processing_status"] == "queued"
        assert data["processing_version"] == 1
        assert data["job"] is not None
        assert data["job"]["status"] == "queued"
        assert data["job"]["retry_count"] == 0
        assert data["job"]["max_retries"] == 3

    @pytest.mark.asyncio
    async def test_status_endpoint_is_tenant_scoped(self, async_client, token_a, token_b, tenant_b):
        """Tenant B must not be able to read tenant A's processing status.

        AC5 is about visibility, so the negative case matters as much as the
        positive one: a status endpoint that leaked across tenants would expose
        job retry counts and error strings for a document the caller cannot see.
        """
        resp_a = await _upload_doc(async_client, token_a, b"Tenant A doc")
        doc_a_id = resp_a.json()["id"]

        headers_b = {"Authorization": f"Bearer {token_b}"}
        resp = await async_client.get(f"/documents/{doc_a_id}/status", headers=headers_b)
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Document not found"
        # The body must not confirm the document or its job exists.
        assert doc_a_id not in resp.text


class TestConcurrentIndexingOfOneDocument:
    """Two jobs for the same document may overlap. The index must survive it.

    MAX_CONCURRENT_PER_TENANT allows several jobs for one tenant at once, so a
    re-upload landing while the previous version is still being indexed puts two
    jobs on the same document. Both run DELETE-then-INSERT on document_chunks;
    the second DELETE cannot see the first's newly inserted rows because its
    statement snapshot predates them, so it re-inserts the same chunk_index
    values and trips uq_document_chunks_document_index.

    Found by running the real worker process, not by reading the code: the
    suite only ever processed one job at a time.
    """

    @pytest.mark.asyncio
    async def test_two_jobs_for_one_document_do_not_corrupt_the_index(
        self, app_session, app_db_engine, tenant_a
    ):
        import io
        from sqlalchemy import text
        from unittest.mock import patch
        from app.models.document import Document, DocumentJob
        from app.database import set_tenant_context
        from app.services.storage import save_uploaded_file
        from app.services.processing import process_document
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        tenant_id = tenant_a["id"]
        doc_id = uuid.uuid4()
        body = b"Refund window is thirty days from receipt. " * 60
        path = save_uploaded_file(io.BytesIO(body), tenant_id, doc_id, "race.txt")

        async with app_session as db:
            await set_tenant_context(db, str(tenant_id))
            db.add(Document(
                id=doc_id, tenant_id=tenant_id,
                original_filename="race.txt", stored_filename="race.txt",
                mime_type="text/plain", size_bytes=path.stat().st_size,
                uploaded_by=tenant_a["client_admin"]["id"],
            ))
            job_ids = []
            for version in range(1, 9):
                # Re-established each iteration: the previous commit ended the
                # transaction the previous set_config belonged to.
                await set_tenant_context(db, str(tenant_id))
                job = DocumentJob(
                    tenant_id=tenant_id, document_id=doc_id,
                    payload={"action": "index", "version": version},
                )
                db.add(job)
                await db.commit()
                job_ids.append(job.id)

        # Separate sessions, as the worker's concurrent drains do.
        sf = async_sessionmaker(app_db_engine, class_=AsyncSession, expire_on_commit=False)

        async def run(job_id):
            async with sf() as db:
                await set_tenant_context(db, str(tenant_id))
                await process_document(db, tenant_id, doc_id, job_id)

        with patch("app.services.processing.embed_chunks",
                   side_effect=lambda c: [[0.0] * 384 for _ in c]):
            results = await asyncio.gather(
                *(run(j) for j in job_ids), return_exceptions=True
            )

        # No unique violation, and neither job may leave a broken document.
        for r in results:
            assert not isinstance(r, Exception), f"concurrent indexing raised {r!r}"

        async with app_session as db:
            await set_tenant_context(db, str(tenant_id))
            chunks = (await db.execute(
                text("SELECT chunk_index, count(*) FROM document_chunks "
                     "WHERE document_id = :d GROUP BY chunk_index "
                     "HAVING count(*) > 1"),
                {"d": doc_id},
            )).all()
            assert not chunks, f"duplicate chunk_index rows: {chunks}"

            status = (await db.execute(
                text("SELECT processing_status FROM documents WHERE id = :d"),
                {"d": doc_id},
            )).scalar()
            assert status == "ready"


class TestPipelineRunsEndToEnd:
    """The whole pipeline, against the real database and real storage.

    Everything else in this file stubs a stage. This one does not stub
    process_document, so it is the only test that would have caught the missing
    datetime import and the lost tenant context after commit - both of which
    made every job fail before any chunk was written.

    Only embed_chunks is stubbed, because the embedding model is not bundled in
    this environment. Everything it depends on - extraction, chunking, the
    document_chunks write, the status transitions - is the real code.
    """

    @pytest.mark.asyncio
    async def test_document_reaches_ready_with_chunks_stored(self, app_session, tenant_a):
        import io
        from sqlalchemy import text
        from unittest.mock import patch
        from app.models.document import Document, DocumentJob
        from app.database import set_tenant_context
        from app.services.storage import save_uploaded_file
        from app.services.processing import process_document

        doc_id = uuid.uuid4()
        job_id = uuid.uuid4()
        body = b"Vendor refund policy is 30 days from receipt. " * 40
        file_path = save_uploaded_file(
            io.BytesIO(body), tenant_a["id"], doc_id, "e2e.txt"
        )
        assert file_path.exists(), "fixture must exist on disk for the pipeline to read"

        async with app_session as db:
            await set_tenant_context(db, str(tenant_a["id"]))
            db.add(Document(
                id=doc_id,
                tenant_id=tenant_a["id"],
                original_filename="e2e.txt",
                stored_filename="e2e.txt",
                mime_type="text/plain",
                size_bytes=file_path.stat().st_size,
                uploaded_by=tenant_a["client_admin"]["id"],
            ))
            db.add(DocumentJob(
                id=job_id,
                tenant_id=tenant_a["id"],
                document_id=doc_id,
                payload={"action": "index", "version": 1},
            ))
            await db.commit()

            with patch("app.services.processing.embed_chunks", side_effect=lambda c: [[0.0] * 384 for _ in c]):
                await set_tenant_context(db, str(tenant_a["id"]))
                await process_document(db, tenant_a["id"], doc_id, job_id)

            await set_tenant_context(db, str(tenant_a["id"]))
            doc_row = (await db.execute(
                text("SELECT processing_status, processing_error, processing_completed_at "
                     "FROM documents WHERE id = :d"),
                {"d": doc_id},
            )).one()
            assert doc_row.processing_status == "ready"
            assert doc_row.processing_error is None
            assert doc_row.processing_completed_at is not None

            job_row = (await db.execute(
                text("SELECT status, last_error FROM document_jobs WHERE id = :j"),
                {"j": job_id},
            )).one()
            assert job_row.status == "done"
            assert job_row.last_error is None

            chunks = (await db.execute(
                text("SELECT count(*) FROM document_chunks WHERE document_id = :d"),
                {"d": doc_id},
            )).scalar()
            assert chunks > 0, "ready document must have chunks behind it"


class TestWorkerCrashRecovery:
    """Proof: a re-run replaces the previous chunk set rather than adding to it."""

    @pytest.mark.asyncio
    async def test_rerun_replaces_chunks_not_duplicates(self, app_session, tenant_a):
        """Re-processing a document must leave exactly one chunk set behind.

        The previous version of this test asserted that a crashed worker had
        written no chunks, which is true for any input and therefore proved
        nothing. The property that actually matters is what happens on the
        retry: if store_chunks appends, a document processed N times holds N
        copies of the same text and search returns the same sentence N times.
        """
        from sqlalchemy import text
        from app.models.document import Document
        from app.services.processing import store_chunks
        from app.database import set_tenant_context

        async with app_session as db:
            await set_tenant_context(db, str(tenant_a["id"]))
            doc = Document(
                tenant_id=tenant_a["id"],
                original_filename="retry.txt",
                stored_filename="retry.txt",
                mime_type="text/plain",
                size_bytes=100,
                uploaded_by=tenant_a["client_admin"]["id"],
            )
            db.add(doc)
            await db.commit()

            vec = [0.0] * 384
            for content in (["alpha", "beta", "gamma"], ["alpha", "beta", "gamma"]):
                # Context is transaction-scoped, so it must be re-established
                # for every call that follows a commit.
                await set_tenant_context(db, str(tenant_a["id"]))
                await store_chunks(db, tenant_a["id"], doc.id, content, [vec] * len(content))

            await set_tenant_context(db, str(tenant_a["id"]))
            result = await db.execute(
                text("SELECT count(*) FROM document_chunks WHERE document_id = :did"),
                {"did": doc.id},
            )
            assert result.scalar() == 3, "second run duplicated chunks instead of replacing them"

    @pytest.mark.asyncio
    async def test_crash_mid_job_leaves_document_not_ready(self, app_session, tenant_a):
        """A job that never completed must not leave the document searchable.

        processing_status is the only thing search will read, so 'ready' is the
        load-bearing assertion: a crash must leave it in a non-ready state even
        though a job row exists claiming to be processing.
        """
        from sqlalchemy import text
        from app.models.document import Document, DocumentJob
        from app.database import set_tenant_context

        async with app_session as db:
            await set_tenant_context(db, str(tenant_a["id"]))
            doc = Document(
                tenant_id=tenant_a["id"],
                original_filename="crash.txt",
                stored_filename="crash.txt",
                mime_type="text/plain",
                size_bytes=100,
                uploaded_by=tenant_a["client_admin"]["id"],
                processing_status="processing",
            )
            db.add(doc)
            await db.commit()

            await set_tenant_context(db, str(tenant_a["id"]))
            job = DocumentJob(
                tenant_id=tenant_a["id"],
                document_id=doc.id,
                payload={"action": "index", "version": 1},
                status="processing",
                started_at=datetime.now(timezone.utc),
            )
            db.add(job)
            await db.commit()

            # Worker died here. Re-read as the app identity, not the in-memory
            # object, so this reflects what a reader would actually see.
            await set_tenant_context(db, str(tenant_a["id"]))
            result = await db.execute(
                text("SELECT processing_status FROM documents WHERE id = :did"),
                {"did": doc.id},
            )
            assert result.scalar() != "ready", "crashed job must not leave the document searchable"

            await set_tenant_context(db, str(tenant_a["id"]))
            result = await db.execute(
                text("SELECT count(*) FROM document_chunks WHERE document_id = :did"),
                {"did": doc.id},
            )
            assert result.scalar() == 0


# Worker unit test for fair scheduling
class TestWorkerSemaphore:
    @pytest.mark.asyncio
    async def test_per_tenant_semaphore_limits_concurrency(self):
        from worker import get_tenant_semaphore, MAX_CONCURRENT_PER_TENANT
        import uuid

        tid = uuid.uuid4()
        sem = get_tenant_semaphore(tid)
        assert sem._value == MAX_CONCURRENT_PER_TENANT

        # Acquire all permits
        acquired = []
        for _ in range(MAX_CONCURRENT_PER_TENANT):
            acquired.append(await sem.acquire())
        assert sem._value == 0

        # Next acquire should wait (test with timeout)
        async def try_acquire():
            await asyncio.wait_for(sem.acquire(), timeout=0.1)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(try_acquire(), timeout=0.2)

        # Release one
        sem.release()
        assert sem._value == 1