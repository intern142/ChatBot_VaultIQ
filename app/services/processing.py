"""VQ-203: Document processing service.

Handles text extraction, chunking, embedding, and indexing of documents.
"""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO
from app.config import get_settings
from app.services.storage import get_document_file_path

settings = get_settings()


def extract_text_from_file(file_path: Path, mime_type: str) -> str:
    """Extract text from a file based on its MIME type.

    Uses existing extraction logic. For now, handles:
    - text/plain, text/markdown, text/csv: direct read
    - application/pdf: uses pypdf
    - application/vnd.openxmlformats-officedocument.wordprocessingml.document: python-docx
    - application/vnd.openxmlformats-officedocument.spreadsheetml.sheet: openpyxl
    - application/msword: antiword or textract (stub)
    - images: OCR via tesseract (stub)

    TODO: Integrate with VQ-201 OCR pipeline when merged.
    """
    ext = file_path.suffix.lower()

    if mime_type in ("text/plain", "text/markdown", "text/csv") or ext in (".txt", ".md", ".csv"):
        return file_path.read_text(encoding="utf-8", errors="replace")

    if mime_type == "application/pdf" or ext == ".pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(file_path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            raise RuntimeError(f"PDF extraction failed: {e}")

    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" or ext == ".docx":
        try:
            import docx
            doc = docx.Document(str(file_path))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as e:
            raise RuntimeError(f"DOCX extraction failed: {e}")

    if mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" or ext == ".xlsx":
        try:
            import openpyxl
            wb = openpyxl.load_workbook(str(file_path), read_only=True, data_only=True)
            texts = []
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True):
                    texts.append(" ".join(str(c) for c in row if c is not None))
            return "\n".join(texts)
        except Exception as e:
            raise RuntimeError(f"XLSX extraction failed: {e}")

    if mime_type == "application/msword" or ext == ".doc":
        # Stub for legacy .doc files
        return "[Legacy .doc format - extraction not implemented]"

    # Images - OCR stub
    if mime_type.startswith("image/") or ext in (".png", ".jpg", ".jpeg", ".tiff", ".tif"):
        # TODO: Integrate tesseract OCR from VQ-201
        return f"[Image OCR not yet implemented: {file_path.name}]"

    # Default: try to read as text
    try:
        return file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return f"[Binary file - no text extraction: {file_path.name}]"


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks by character count.

    Simple character-based chunking. For production, use token-based chunking
    with the embedding model's tokenizer.
    """
    if not text.strip():
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]
        chunks.append(chunk)
        if end == len(text):
            break
        start = end - overlap
        if start < 0:
            start = 0
    return chunks


async def process_document(
    db,
    tenant_id: uuid.UUID,
    document_id: uuid.UUID,
    job_id: uuid.UUID,
) -> None:
    """Main processing pipeline for a document.

    Steps:
    1. Load file from storage
    2. Extract text
    3. Chunk text
    4. Embed chunks (FastEmbed)
    5. Store chunks + embeddings in pgvector
    6. Mark job done, document ready

    Raises exceptions on failure for retry logic.

    Every commit below ends the transaction, and the tenant context is set with
    set_config(..., is_local=true), which does not survive a commit. Each write
    that follows a commit therefore re-establishes the context first. Without
    that the UPDATE runs as a no-tenant session, the RLS policy hides the row,
    and SQLAlchemy raises StaleDataError or ObjectDeletedError instead of
    writing. The job's tenant_id is used rather than a caller-supplied value,
    and it is the same tenant the row was selected under.
    """
    from app.models.document import Document, DocumentJob, ProcessingStatus, JobStatus
    from sqlalchemy import select
    from app.database import set_tenant_context

    # Set tenant context for RLS
    await set_tenant_context(db, str(tenant_id))

    # Load document and job
    doc_result = await db.execute(select(Document).where(Document.id == document_id))
    document = doc_result.scalar_one_or_none()
    job_result = await db.execute(select(DocumentJob).where(DocumentJob.id == job_id))
    job = job_result.scalar_one_or_none()

    if not document or not job:
        raise RuntimeError("Document or job not found")

    # Update status to processing
    document.processing_status = ProcessingStatus.processing
    document.processing_started_at = datetime.now(timezone.utc)
    job.status = JobStatus.processing
    job.started_at = datetime.now(timezone.utc)
    await db.commit()

    try:
        # 1. Get file path
        file_path = get_document_file_path(tenant_id, document_id, document.stored_filename)
        if not file_path.exists():
            raise FileNotFoundError(f"Document file not found: {file_path}")

        # 2. Extract text
        text = extract_text_from_file(file_path, document.mime_type)
        if not text.strip():
            raise RuntimeError("No text extracted from document")

        # 3. Chunk text
        chunks = chunk_text(text)
        if not chunks:
            raise RuntimeError("No chunks generated from document")

        # 4. Embed chunks (FastEmbed)
        embeddings = embed_chunks(chunks)

        # 5. Store chunks + embeddings. store_chunks commits, which drops the
        # context again, so it is re-established before the status writes below.
        await store_chunks(db, tenant_id, document_id, chunks, embeddings)

        # 6. Success - mark job done, document ready
        await set_tenant_context(db, str(tenant_id))
        document.processing_status = ProcessingStatus.ready
        document.processing_completed_at = datetime.now(timezone.utc)
        document.processing_error = None
        job.status = JobStatus.done
        job.completed_at = datetime.now(timezone.utc)
        job.last_error = None
        await db.commit()

    except Exception as e:
        # Failure - will be handled by caller for retry logic
        await set_tenant_context(db, str(tenant_id))
        document.processing_status = ProcessingStatus.failed
        document.processing_error = str(e)
        job.status = JobStatus.failed
        job.completed_at = datetime.now(timezone.utc)
        job.last_error = str(e)
        await db.commit()
        raise


def embed_chunks(chunks: list[str]) -> list[list[float]]:
    """Generate embeddings for text chunks using FastEmbed.

    Returns list of embedding vectors (one per chunk).
    """
    try:
        from fastembed import TextEmbedding
        model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        return list(model.embed(chunks))
    except Exception as e:
        raise RuntimeError(f"Embedding failed: {e}")


async def store_chunks(
    db,
    tenant_id: uuid.UUID,
    document_id: uuid.UUID,
    chunks: list[str],
    embeddings: list[list[float]],
) -> None:
    """Store text chunks and their embeddings.

    The document_chunks table is created by migration 160ccbed24a5, not here.
    Doing DDL from the application fails anyway: vaultiq_app has no CREATE on
    schema public, so the worker would be unable to run its own pipeline.
    """
    from sqlalchemy import text
    from app.database import set_tenant_context

    await set_tenant_context(db, str(tenant_id))

    # Serialise the rewrite for this one document. MAX_CONCURRENT_PER_TENANT
    # allows several jobs for one tenant at once, so two jobs for the *same*
    # document can overlap - which is what happens when a client re-uploads
    # while the previous version is still being indexed. Both would then run
    # DELETE-then-INSERT, and the second DELETE cannot see the first's newly
    # inserted rows because its statement snapshot predates them, so it
    # re-inserts the same chunk_index values and trips
    # uq_document_chunks_document_index, leaving the index holding a mix of
    # two versions.
    #
    # Taken here rather than in process_document because this is the
    # transaction that does the delete and the insert: process_document commits
    # several times before reaching it, and a transaction-scoped lock would be
    # released by each of those commits. Held until the commit below, then
    # released automatically - it cannot leak if the job dies. Scoped to the
    # document, not the tenant, so parallelism between documents is unaffected.
    await db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:doc_id, 0))"),
        {"doc_id": str(document_id)},
    )

    # Rewrite in one statement so a retried job cannot leave a half-updated
    # chunk set behind: the old rows are removed and the new ones inserted
    # inside this transaction, under the lock taken above.
    await db.execute(
        text("DELETE FROM document_chunks WHERE document_id = :document_id"),
        {"document_id": document_id},
    )

    for idx, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        # Format embedding for pgvector: comma-separated, no newlines
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
        await db.execute(
            text("""
                INSERT INTO document_chunks
                    (tenant_id, document_id, chunk_index, content, embedding)
                VALUES (:tenant_id, :document_id, :chunk_index, :content, :embedding)
            """),
            {
                "tenant_id": tenant_id,
                "document_id": document_id,
                "chunk_index": idx,
                "content": chunk,
                "embedding": embedding_str,
            },
        )

    await db.commit()