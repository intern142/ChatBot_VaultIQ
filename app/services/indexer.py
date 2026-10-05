import uuid
import threading
import time
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import OperationalError

from app.database import async_session_maker
from app.models.document import Document
from app.models.search import DocumentChunk, IndexingJob
from app.services.chunking import chunk_document
from app.services.embeddings import embed_texts, get_embedding_dimension
from app.config import get_settings


settings = get_settings()
logger = logging.getLogger(__name__)

# Tenant-scoped concurrency control
_TENANT_SEMAPHORES: dict[uuid.UUID, threading.BoundedSemaphore] = {}
_SEMAPHORE_LOCK = threading.Lock()
MAX_CONCURRENT_PER_TENANT = getattr(settings, 'INDEXING_MAX_CONCURRENT_PER_TENANT', 2)


def get_tenant_semaphore(tenant_id: uuid.UUID) -> threading.BoundedSemaphore:
    """Get or create a semaphore for a tenant."""
    with _SEMAPHORE_LOCK:
        if tenant_id not in _TENANT_SEMAPHORES:
            _TENANT_SEMAPHORES[tenant_id] = threading.BoundedSemaphore(MAX_CONCURRENT_PER_TENANT)
        return _TENANT_SEMAPHORES[tenant_id]


async def enqueue_indexing_job(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    document_id: uuid.UUID,
) -> IndexingJob:
    """Create a new indexing job for a document."""
    job = IndexingJob(
        tenant_id=tenant_id,
        document_id=document_id,
        status='pending',
        attempts=0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def get_pending_jobs(db: AsyncSession, tenant_id: uuid.UUID, limit: int = 10) -> list[IndexingJob]:
    """Get pending indexing jobs for a tenant."""
    result = await db.execute(
        select(IndexingJob)
        .where(
            IndexingJob.tenant_id == tenant_id,
            IndexingJob.status == 'pending'
        )
        .order_by(IndexingJob.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return list(result.scalars().all())


async def process_indexing_job(job_id: uuid.UUID) -> bool:
    """
    Process a single indexing job.
    Returns True if successful, False if failed (will retry).
    """
    async with async_session_maker() as db:
        try:
            # Lock the job
            result = await db.execute(
                select(IndexingJob)
                .where(IndexingJob.id == job_id)
                .with_for_update(skip_locked=True)
            )
            job = result.scalar_one_or_none()
            
            if not job or job.status != 'pending':
                return False

            # Mark as started
            job.status = 'processing'
            job.started_at = datetime.now(timezone.utc)
            job.attempts += 1
            await db.commit()

            # Acquire tenant semaphore
            semaphore = get_tenant_semaphore(job.tenant_id)
            acquired = semaphore.acquire(timeout=300)  # 5 min max wait
            if not acquired:
                job.status = 'pending'
                job.started_at = None
                job.error = 'Could not acquire tenant semaphore'
                await db.commit()
                return False

            try:
                # Get document with extracted text
                doc_result = await db.execute(
                    select(Document).where(Document.id == job.document_id)
                )
                document = doc_result.scalar_one_or_none()
                
                if not document:
                    job.status = 'failed'
                    job.error = 'Document not found'
                    job.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                    return False

                if not document.extracted_text:
                    job.status = 'failed'
                    job.error = 'No extracted text available'
                    job.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                    return False

                # Delete existing chunks for this document
                await db.execute(
                    text("DELETE FROM document_chunks WHERE document_id = :doc_id"),
                    {"doc_id": job.document_id}
                )

                # Chunk the document
                chunks = chunk_document(document.extracted_text)
                if not chunks:
                    job.status = 'completed'
                    job.completed_at = datetime.now(timezone.utc)
                    document.indexed_at = datetime.now(timezone.utc)
                    await db.commit()
                    return True

                # Generate embeddings
                chunk_texts = [c.content for c in chunks]
                embeddings = embed_texts(chunk_texts)

                # Insert chunks
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                    doc_chunk = DocumentChunk(
                        tenant_id=job.tenant_id,
                        document_id=job.document_id,
                        chunk_index=i,
                        content=chunk.content,
                        embedding=embedding,
                    )
                    db.add(doc_chunk)

                # Mark job and document as complete
                job.status = 'completed'
                job.completed_at = datetime.now(timezone.utc)
                document.indexed_at = datetime.now(timezone.utc)
                await db.commit()
                logger.info(f"Indexed document {job.document_id} into {len(chunks)} chunks")
                return True

            except Exception as e:
                logger.exception(f"Error processing indexing job {job_id}")
                job.status = 'failed' if job.attempts >= 3 else 'pending'
                job.error = str(e)[:500]
                job.completed_at = datetime.now(timezone.utc) if job.attempts >= 3 else None
                await db.commit()
                return False

            finally:
                semaphore.release()

        except OperationalError as e:
            logger.error(f"Database error in process_indexing_job: {e}")
            return False


async def run_indexing_worker(tenant_id: uuid.UUID, poll_interval: float = 5.0) -> None:
    """
    Run the indexing worker for a specific tenant.
    This is meant to be run as a background task.
    """
    logger.info(f"Starting indexing worker for tenant {tenant_id}")
    
    while True:
        try:
            async with async_session_maker() as db:
                jobs = await get_pending_jobs(db, tenant_id, limit=5)
                
            if not jobs:
                await asyncio.sleep(poll_interval)
                continue

            for job in jobs:
                await process_indexing_job(job.id)

        except Exception as e:
            logger.exception(f"Error in indexing worker for tenant {tenant_id}")
            await asyncio.sleep(poll_interval)


# Import asyncio at module level for the worker
import asyncio