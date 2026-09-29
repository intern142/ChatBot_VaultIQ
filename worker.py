"""VQ-203: Document processing worker.

Background worker that dequeues and processes document jobs with per-tenant
fair scheduling and retry logic.
"""

import asyncio
import os
import signal
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import get_settings
from app.database import set_tenant_context
from app.models.document import Document, DocumentJob, ProcessingStatus, JobStatus
from app.services.processing import process_document

settings = get_settings()

# Worker configuration
WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "4"))
MAX_CONCURRENT_PER_TENANT = int(os.getenv("MAX_CONCURRENT_PER_TENANT", "2"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
BASE_RETRY_DELAY_SECONDS = int(os.getenv("BASE_RETRY_DELAY_SECONDS", "30"))

# Per-tenant semaphores for fair scheduling
_tenant_semaphores: dict[uuid.UUID, asyncio.Semaphore] = {}


def get_tenant_semaphore(tenant_id: uuid.UUID) -> asyncio.Semaphore:
    """Get or create a semaphore for a tenant."""
    if tenant_id not in _tenant_semaphores:
        _tenant_semaphores[tenant_id] = asyncio.Semaphore(MAX_CONCURRENT_PER_TENANT)
    return _tenant_semaphores[tenant_id]


# Rotating cursor for round-robin dequeue. Module level, in-process only:
# with multiple worker processes each keeps its own cursor, which still gives
# per-process fairness and the SKIP LOCKED claim below keeps them from
# colliding on the same row.
_tenant_cursor = 0


async def list_active_tenants(db: AsyncSession) -> list[uuid.UUID]:
    """List the ids of tenants with work the worker may consider.

    This is the only query the worker runs without a tenant context. It is
    safe by construction rather than by policy: the `tenants` table is
    platform metadata (id, short_code, name, status) granted to vaultiq_app by
    migration 005, it holds no customer content, and it is the same list a
    Super Admin already sees. No row from `documents`, `document_chunks` or
    any content table is touched here.

    The alternative - a dedicated worker role that can read every job row
    across every tenant - would widen what a database identity can see in
    order to fix a scheduling problem. This does not.
    """
    from app.models.tenant import Tenant

    result = await db.execute(
        select(Tenant.id)
        .where(Tenant.status.in_(("active", "suspended")))
        .order_by(Tenant.id.asc())
    )
    return [row[0] for row in result.all()]


async def dequeue_job(db: AsyncSession, tenant_id: uuid.UUID) -> DocumentJob | None:
    """Dequeue the oldest queued job for one tenant.

    FOR UPDATE SKIP LOCKED so two workers cannot claim the same row.
    Returns None if this tenant has nothing queued.
    """
    await set_tenant_context(db, str(tenant_id))
    result = await db.execute(
        select(DocumentJob)
        .where(
            DocumentJob.status == "queued",
            DocumentJob.tenant_id == tenant_id,
        )
        .order_by(DocumentJob.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if job is None:
        await db.rollback()
    return job


async def dequeue_any_job(db: AsyncSession) -> DocumentJob | None:
    """Claim one queued job, round-robin across tenants.

    A no-tenant session sees zero rows of document_jobs, so a bare
    `WHERE status='queued'` SELECT always returns nothing and the worker
    spins on a permanently empty queue. Instead of widening a database role to
    fix that, walk the tenant list and dequeue inside each tenant's own
    context - the same path the HTTP layer uses, already proven by the RLS
    tests.

    The cursor advances on every call so a tenant with a deep queue cannot
    starve a tenant with a single job, which is AC3.
    """
    global _tenant_cursor

    tenant_ids = await list_active_tenants(db)
    if not tenant_ids:
        return None

    start = _tenant_cursor % len(tenant_ids)
    for offset in range(len(tenant_ids)):
        tenant_id = tenant_ids[(start + offset) % len(tenant_ids)]
        job = await dequeue_job(db, tenant_id)
        if job is not None:
            _tenant_cursor = (start + offset + 1) % len(tenant_ids)
            return job

    # Every tenant was empty; the tenant-list query is still open.
    await db.rollback()
    return None


async def process_job(db: AsyncSession, job: DocumentJob) -> None:
    """Process a single job with retry logic."""
    from app.services.processing import process_document

    tenant_id = job.tenant_id
    document_id = job.document_id

    # Acquire tenant semaphore for fair scheduling
    semaphore = get_tenant_semaphore(tenant_id)
    async with semaphore:
        # Set tenant context
        await set_tenant_context(db, str(tenant_id))

        try:
            await process_document(db, tenant_id, document_id, job.id)
        except Exception as e:
            # The context is transaction-scoped and process_document committed
            # before it raised, so it must be re-established here. Without this
            # the retry UPDATE matches no rows under RLS and the job is neither
            # re-queued nor marked failed - it silently disappears.
            await set_tenant_context(db, str(tenant_id))
            # Retry logic
            if job.retry_count < job.max_retries:
                job.retry_count += 1
                job.status = JobStatus.queued
                job.last_error = str(e)
                # Exponential backoff: schedule for later
                delay = BASE_RETRY_DELAY_SECONDS * (2 ** (job.retry_count - 1))
                job.created_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                await db.commit()
                # Log retry
                print(f"Job {job.id} failed, retry {job.retry_count}/{job.max_retries} in {delay}s: {e}")
            else:
                # Max retries exceeded - mark as failed
                job.status = JobStatus.failed
                job.completed_at = datetime.now(timezone.utc)
                job.last_error = f"Max retries exceeded: {e}"
                await db.commit()
                print(f"Job {job.id} failed permanently after {job.max_retries} retries: {e}")


async def worker_loop(engine) -> None:
    """Main worker loop - runs continuously."""
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print(f"Worker started (concurrency={WORKER_CONCURRENCY}, max_per_tenant={MAX_CONCURRENT_PER_TENANT})")

    # WORKER_CONCURRENCY was previously read from the environment and never
    # used: the loop below processed one job at a time. Per-tenant fairness
    # comes from the semaphores in process_job and the round-robin cursor in
    # dequeue_any_job, neither of which needs a global cap, but the pool still
    # needs one so a single process cannot exhaust its own connections.
    inflight: set[asyncio.Task] = set()

    async def drain() -> DocumentJob | None:
        async with session_factory() as db:
            job = await dequeue_any_job(db)
            if job is None:
                return None
            await process_job(db, job)
            return job

    while True:
        try:
            # Top up towards the cap. Each task opens its own session, so
            # concurrent drains do not share a transaction.
            while len(inflight) < WORKER_CONCURRENCY:
                inflight.add(asyncio.create_task(drain()))

            done, inflight = await asyncio.wait(
                inflight, timeout=0.5, return_when=asyncio.FIRST_COMPLETED
            )

            if not done:
                continue

            for task in done:
                # Retrieve the result or exception either way. An exception left
                # unretrieved is logged as "Task exception was never retrieved"
                # and the loop carries on silently, which is how a queue that
                # never drains can look like a worker that is merely idle.
                exc = task.exception()
                if exc is not None:
                    print(f"Worker error: {exc}")
                else:
                    await asyncio.sleep(0)

            if not inflight and not any(not t.done() for t in done):
                # Nothing queued anywhere; back off instead of spinning.
                await asyncio.sleep(1)
        except Exception as e:
            print(f"Worker error: {e}")
            await asyncio.sleep(5)


async def main():
    """Main entry point."""
    settings = get_settings()
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=WORKER_CONCURRENCY + 2,
        max_overflow=0,
    )

    # Graceful shutdown
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def signal_handler():
        print("Shutdown signal received")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass

    # Run worker
    await worker_loop(engine)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())