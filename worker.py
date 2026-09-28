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


async def dequeue_job(db: AsyncSession) -> DocumentJob | None:
    """Dequeue the next available job using fair scheduling.

    Uses FOR UPDATE SKIP LOCKED to avoid conflicts between workers.
    Returns the next queued job or None if queue is empty.
    """
    result = await db.execute(
        select(DocumentJob)
        .where(DocumentJob.status == "queued")
        .order_by(DocumentJob.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    return result.scalar_one_or_none()


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
            # Retry logic
            if job.retry_count < job.max_retries:
                job.retry_count += 1
                job.status = "queued"
                job.last_error = str(e)
                # Exponential backoff: schedule for later
                delay = BASE_RETRY_DELAY_SECONDS * (2 ** (job.retry_count - 1))
                job.created_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
                await db.commit()
                # Log retry
                print(f"Job {job.id} failed, retry {job.retry_count}/{job.max_retries} in {delay}s: {e}")
            else:
                # Max retries exceeded - mark as failed
                job.status = "failed"
                job.completed_at = datetime.now(timezone.utc)
                job.last_error = f"Max retries exceeded: {e}"
                await db.commit()
                print(f"Job {job.id} failed permanently after {job.max_retries} retries: {e}")


async def worker_loop(engine) -> None:
    """Main worker loop - runs continuously."""
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print(f"Worker started (concurrency={WORKER_CONCURRENCY}, max_per_tenant={MAX_CONCURRENT_PER_TENANT})")

    while True:
        try:
            async with session_factory() as db:
                # Dequeue next job
                job = await dequeue_job(db)
                if job:
                    await process_job(db, job)
                else:
                    # No jobs - short sleep
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