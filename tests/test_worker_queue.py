"""VQ-203: the worker's claim path, exercised against the real RLS policies.

The first VQ-203 commit had no test that called dequeue_job. The queue
accepted uploads and nothing was ever claimed, and the suite was green,
because every test in the file either called process_job directly with a job
object it had already constructed, or bypassed the queue entirely.

dequeue_any_job is the only place a job crosses from the queue into a tenant
context, so it is what these tests drive. They run as vaultiq_app
(NOBYPASSRLS) through the app_session fixture. Under the superuser they would
pass regardless of the policy, which is the failure mode being guarded against.
"""

import uuid

import pytest
from sqlalchemy import text

from app.database import set_tenant_context
from app.models.document import Document, DocumentJob, JobStatus
from worker import dequeue_any_job, dequeue_job, list_active_tenants


async def _make_job(db, tenant, document_id, index):
    # The context is transaction-scoped, so it has to be re-established for
    # every job: the commit in the previous iteration ended the transaction
    # that the previous set_config belonged to. Without this the second insert
    # in the loop runs as a no-tenant session and RLS rejects it.
    await set_tenant_context(db, str(tenant["id"]))
    job = DocumentJob(
        tenant_id=tenant["id"],
        document_id=document_id,
        payload={"action": "index", "version": index + 1},
    )
    db.add(job)
    await db.commit()
    return job


@pytest.mark.asyncio
class TestWorkerCanSeeTheQueue:
    async def test_claimed_job_is_visible_to_a_no_tenant_session_once_context_is_set(
        self, app_session, tenant_a, tenant_b
    ):
        """The claim must work under RLS, not only under the superuser.

        A bare `SELECT ... WHERE status='queued'` with no tenant context returns
        zero rows here, which is the original defect: the worker saw a
        permanently empty queue. dequeue_any_job gets around it by walking the
        tenant list and setting a context per tenant, so it must find the job.
        """
        doc_id = uuid.uuid4()
        job_id = uuid.uuid4()

        async with app_session as db:
            await set_tenant_context(db, str(tenant_a["id"]))
            db.add(Document(
                id=doc_id, tenant_id=tenant_a["id"],
                original_filename="a.txt", stored_filename="a.txt",
                mime_type="text/plain", size_bytes=1,
                uploaded_by=tenant_a["client_admin"]["id"],
            ))
            db.add(DocumentJob(
                id=job_id, tenant_id=tenant_a["id"], document_id=doc_id,
                payload={"action": "index", "version": 1},
            ))
            await db.commit()

            # Confirm the premise: no context, no rows.
            no_context = (await db.execute(
                text("SELECT count(*) FROM document_jobs WHERE status='queued'")
            )).scalar()
            assert no_context == 0, (
                "expected the no-tenant blind spot; if this is nonzero the "
                "policy is not actually protecting the table"
            )

            # The claim path must still find it.
            claimed = await dequeue_any_job(db)
            assert claimed is not None, "worker saw an empty queue under RLS"
            assert claimed.id == job_id

    async def test_list_active_tenants_reads_metadata_only(self, app_session, tenant_a, tenant_b):
        """The one no-tenant query must not expose customer content.

        This is the whole basis for allowing the worker to enumerate tenants
        without a new database role. If this query ever grows a join to
        documents or chunks, Rule 1 and Rule 4 are both broken.
        """
        async with app_session as db:
            tenant_ids = await list_active_tenants(db)

        assert tenant_a["id"] in tenant_ids
        assert tenant_b["id"] in tenant_ids

        import ast
        import inspect
        import worker
        # Strip the docstring before scanning - it names the forbidden tables
        # precisely in order to explain why they are not queried.
        tree = ast.parse(inspect.getsource(worker.list_active_tenants).lstrip())
        fn = tree.body[0]
        if (fn.body and isinstance(fn.body[0], ast.Expr)
                and isinstance(fn.body[0].value, ast.Constant)
                and isinstance(fn.body[0].value.value, str)):
            fn.body = fn.body[1:]
        body = ast.unparse(fn)
        for forbidden in ("Document", "document_chunks", "documents"):
            assert forbidden not in body, (
                f"list_active_tenants must stay on the tenants table, found {forbidden}"
            )

    async def test_worker_needs_no_elevated_role(self, app_session):
        """The worker runs as vaultiq_app, which needs no new grants.

        Recorded as a test so that a future 'fix' that adds a SECURITY DEFINER
        function or a worker-specific role has to come back and justify itself.
        """
        async with app_session as db:
            result = await db.execute(text("SELECT current_user"))
            assert result.scalar() == "vaultiq_app"

            for table, privilege in (
                ("document_jobs", "SELECT"),
                ("tenants", "SELECT"),
            ):
                has = (await db.execute(
                    text("SELECT has_table_privilege(current_user, :t, :p)"),
                    {"t": table, "p": privilege},
                )).scalar()
                assert has is True, f"vaultiq_app needs {privilege} on {table}"

            # And it must not have been handed blanket bypass.
            bypass = (await db.execute(
                text("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user")
            )).scalar()
            assert bypass is False, "worker identity must not have BYPASSRLS"


@pytest.mark.asyncio
class TestWorkerCannotCrossTenants:
    async def test_dequeue_never_returns_another_tenants_job(self, app_session, tenant_a, tenant_b):
        """A context for tenant A must not yield tenant B's job.

        dequeue_job filters on tenant_id in addition to relying on the policy.
        The filter is defence in depth: if the policy were ever loosened, the
        application query still refuses.
        """
        doc_b = uuid.uuid4()
        job_b = uuid.uuid4()

        async with app_session as db:
            await set_tenant_context(db, str(tenant_b["id"]))
            db.add(Document(
                id=doc_b, tenant_id=tenant_b["id"],
                original_filename="b.txt", stored_filename="b.txt",
                mime_type="text/plain", size_bytes=1,
                uploaded_by=tenant_b["client_admin"]["id"],
            ))
            db.add(DocumentJob(
                id=job_b, tenant_id=tenant_b["id"], document_id=doc_b,
                payload={"action": "index", "version": 1},
            ))
            await db.commit()

            # Ask for tenant A's work. There is none, and B's job is not it.
            claimed = await dequeue_job(db, tenant_a["id"])
            assert claimed is None, "tenant A's context returned tenant B's job"

            # Tenant B can still get its own.
            claimed_b = await dequeue_job(db, tenant_b["id"])
            assert claimed_b is not None
            assert claimed_b.id == job_b
            assert claimed_b.tenant_id == tenant_b["id"]


@pytest.mark.asyncio
class TestWorkerFairness:
    async def test_busy_tenant_cannot_starve_a_quiet_one(self, app_session, tenant_a, tenant_b):
        """AC3: a tenant with a deep queue must not delay a tenant with one job.

        Tenant A gets 5 queued jobs and tenant B gets 1. Round-robin has to
        reach B well before A is exhausted; a global `ORDER BY created_at`
        with a fixed start would return A's jobs every time and B would wait
        for all five.
        """
        doc_a, doc_b = uuid.uuid4(), uuid.uuid4()

        async with app_session as db:
            for tenant, doc_id in ((tenant_a, doc_a), (tenant_b, doc_b)):
                await set_tenant_context(db, str(tenant["id"]))
                db.add(Document(
                    id=doc_id, tenant_id=tenant["id"],
                    original_filename="f.txt", stored_filename="f.txt",
                    mime_type="text/plain", size_bytes=1,
                    uploaded_by=tenant["client_admin"]["id"],
                ))
                await db.commit()

            await set_tenant_context(db, str(tenant_a["id"]))
            for i in range(5):
                await _make_job(db, tenant_a, doc_a, i)

            await set_tenant_context(db, str(tenant_b["id"]))
            await _make_job(db, tenant_b, doc_b, 0)

            # Claim until tenant B's job comes out.
            b_position = None
            for attempt in range(10):
                claimed = await dequeue_any_job(db)
                if claimed is None:
                    break
                if claimed.tenant_id == tenant_b["id"]:
                    b_position = attempt
                    break
                # Release it so it does not skew the rest of the loop.
                await set_tenant_context(db, str(claimed.tenant_id))
                claimed.status = JobStatus.queued
                await db.commit()

            assert b_position is not None, "tenant B's job was never claimed"
            assert b_position <= 2, (
                f"tenant B waited behind {b_position} of tenant A's jobs; "
                "round-robin is not preventing starvation"
            )
