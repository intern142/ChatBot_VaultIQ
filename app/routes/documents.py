import asyncio
import uuid
import mimetypes
import magic
from typing import BinaryIO
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Query, Form
from fastapi.responses import FileResponse
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth.dependencies import get_current_user_with_tenant
from app.auth.permissions import require_roles_with_tenant
from app.models.document import Document
from app.models.user import User
from app.models.tenant import Tenant
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    StorageUsageResponse,
)
from app.services.storage import (
    save_uploaded_file,
    delete_document_file,
    get_document_file_path,
)
from app.services.file_detection import detect_document_mime
from app.services.storage import UploadTooLargeError
from app.services.ocr import (
    DocumentExtractionError,
    OcrUnavailableError,
    extract_document_text,
)
from app.config import get_settings

router = APIRouter(prefix="/documents", tags=["documents"])

settings = get_settings()

# Parse allowed MIME types from settings (comma-separated string)
ALLOWED_MIME_TYPES = {m.strip() for m in settings.ALLOWED_MIME_TYPES.split(",") if m.strip()}

MAX_FILE_SIZE = settings.MAX_FILE_SIZE_MB * 1024 * 1024


def validate_file_size(file: UploadFile) -> None:
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {settings.MAX_FILE_SIZE_MB}MB"
        )


def validate_mime_type(file: UploadFile) -> str:
    """Validate MIME type from file CONTENT using python-magic.
    
    Returns the detected MIME type if allowed.
    Raises HTTPException if not allowed or detection fails.
    """
    # Read first 8192 bytes for MIME detection
    file.file.seek(0)
    header = file.file.read(8192)
    file.file.seek(0)

    if not header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file"
        )

    detected_mime = magic.from_buffer(header, mime=True)
    detected_mime = detect_document_mime(file.file, detected_mime)

    if detected_mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type: {detected_mime}. Allowed: {', '.join(sorted(ALLOWED_MIME_TYPES))}"
        )

    return detected_mime


async def check_quota(db: AsyncSession, tenant_id: uuid.UUID, additional_bytes: int) -> None:
    """Check if tenant has enough quota for additional bytes.
    
    Raises HTTPException 413 if quota would be exceeded.
    """
    await db.execute(
        select(func.pg_advisory_xact_lock(func.hashtext(str(tenant_id))))
    )
    # Get current usage
    usage_result = await db.execute(
        select(func.coalesce(func.sum(Document.size_bytes), 0))
        .where(Document.tenant_id == tenant_id)
    )
    current_bytes = usage_result.scalar() or 0

    # Get tenant quota
    quota_result = await db.execute(
        select(Tenant.storage_quota_mb).where(Tenant.id == tenant_id)
    )
    quota_mb = quota_result.scalar() or 0
    quota_bytes = quota_mb * 1024 * 1024

    if current_bytes + additional_bytes > quota_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Storage quota exceeded. Used: {current_bytes / (1024*1024):.2f}MB, "
                   f"Quota: {quota_mb}MB, File: {additional_bytes / (1024*1024):.2f}MB"
        )


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form(...),
    current_user_tenant: tuple[User, str] = Depends(require_roles_with_tenant("client_admin")),
    db: AsyncSession = Depends(get_db),
):
    current_user, tenant_id_str = current_user_tenant
    tenant_id = uuid.UUID(tenant_id_str)

    # Validate category
    valid_categories = {"policy", "hr", "sop", "process", "other"}
    if category not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category. Must be one of: {', '.join(sorted(valid_categories))}"
        )

    # Validate file size (fast check from header)
    validate_file_size(file)

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required"
        )

    # Validate MIME type from CONTENT (authoritative check)
    detected_mime = validate_mime_type(file)

    # Check quota BEFORE saving file
    await check_quota(db, tenant_id, file.size or 0)

    document_id = uuid.uuid4()
    extension = mimetypes.guess_extension(detected_mime) or ".bin"
    stored_filename = f"{document_id}{extension}"

    file_saved = False
    document = None
    try:
        file_path = save_uploaded_file(
            file.file,
            tenant_id,
            document_id,
            stored_filename,
            MAX_FILE_SIZE
        )
        file_saved = True
        actual_size = file_path.stat().st_size
        if actual_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Max size: {settings.MAX_FILE_SIZE_MB}MB"
            )
        extraction = await asyncio.to_thread(extract_document_text, file_path, detected_mime)
        await check_quota(db, tenant_id, actual_size)

        document = Document(
            id=document_id,
            tenant_id=tenant_id,
            original_filename=file.filename,
            stored_filename=stored_filename,
            mime_type=detected_mime,
            size_bytes=actual_size,
            uploaded_by=current_user.id,
            category=category,
            extracted_text=extraction.text,
            extraction_method=extraction.method,
            extraction_status=extraction.status,
            extraction_page_count=extraction.page_count,
            extraction_truncated=extraction.truncated,
        )
        db.add(document)
        await db.flush()
        await db.refresh(document)
        await db.commit()
    except HTTPException:
        await db.rollback()
        if file_saved:
            delete_document_file(tenant_id, document_id, stored_filename)
        raise
    except UploadTooLargeError as exc:
        await db.rollback()
        if file_saved:
            delete_document_file(tenant_id, document_id, stored_filename)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {settings.MAX_FILE_SIZE_MB}MB"
        ) from exc
    except OcrUnavailableError as exc:
        await db.rollback()
        if file_saved:
            delete_document_file(tenant_id, document_id, stored_filename)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Offline text extraction is unavailable",
        ) from exc
    except DocumentExtractionError as exc:
        await db.rollback()
        if file_saved:
            delete_document_file(tenant_id, document_id, stored_filename)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Document text extraction failed",
        ) from exc
    except Exception:
        await db.rollback()
        if file_saved:
            delete_document_file(tenant_id, document_id, stored_filename)
        raise

    return document


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user_tenant: tuple[User, str] = Depends(require_roles_with_tenant("client_admin", "employee")),
    db: AsyncSession = Depends(get_db),
):
    _, tenant_id = current_user_tenant

    offset = (page - 1) * page_size

    # Get total count
    total_result = await db.execute(
        select(func.count(Document.id)).where(Document.tenant_id == uuid.UUID(tenant_id))
    )
    total = total_result.scalar() or 0

    # Get documents
    result = await db.execute(
        select(Document)
        .where(Document.tenant_id == uuid.UUID(tenant_id))
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    documents = result.scalars().all()

    return DocumentListResponse(
        documents=documents,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/usage", response_model=StorageUsageResponse)
async def get_storage_usage(
    current_user_tenant: tuple[User, str] = Depends(require_roles_with_tenant("client_admin")),
    db: AsyncSession = Depends(get_db),
):
    _, tenant_id = current_user_tenant

    result = await db.execute(
        select(
            func.count(Document.id).label("total_documents"),
            func.coalesce(func.sum(Document.size_bytes), 0).label("total_size_bytes")
        ).where(Document.tenant_id == uuid.UUID(tenant_id))
    )
    row = result.one()

    total_size_bytes = row.total_size_bytes
    total_size_mb = total_size_bytes / (1024 * 1024)

    return StorageUsageResponse(
        tenant_id=uuid.UUID(tenant_id),
        total_documents=row.total_documents,
        total_size_bytes=total_size_bytes,
        total_size_mb=round(total_size_mb, 2),
    )


@router.get("/{document_id}/preview")
async def preview_document(
    document_id: uuid.UUID,
    current_user_tenant: tuple[User, str] = Depends(require_roles_with_tenant("client_admin", "employee")),
    db: AsyncSession = Depends(get_db),
):
    _, tenant_id = current_user_tenant

    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == uuid.UUID(tenant_id)
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    file_path = get_document_file_path(
        uuid.UUID(tenant_id), document_id, document.stored_filename
    )

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found"
        )

    preview_chars = 5000
    if document.extracted_text:
        return {
            "document_id": str(document.id),
            "filename": document.original_filename,
            "mime_type": document.mime_type,
            "preview": document.extracted_text[:preview_chars],
            "truncated": document.extraction_truncated or len(document.extracted_text) > preview_chars,
            "extraction_status": document.extraction_status,
        }

    if document.mime_type.startswith("text/"):
        content = file_path.read_text(encoding="utf-8", errors="replace")
        return {
            "document_id": str(document.id),
            "filename": document.original_filename,
            "mime_type": document.mime_type,
            "preview": content[:preview_chars],
            "truncated": len(content) > preview_chars,
            "extraction_status": document.extraction_status,
        }

    message = "Preview not available for this file type"
    if document.extraction_status == "no_text":
        message = "No text detected"
    elif document.extraction_status == "unavailable":
        message = "Text extraction unavailable"

    return {
        "document_id": str(document.id),
        "filename": document.original_filename,
        "mime_type": document.mime_type,
        "size_bytes": document.size_bytes,
        "preview": None,
        "message": message,
        "extraction_status": document.extraction_status,
    }


@router.get("/{document_id}/download")
async def download_document(
    document_id: uuid.UUID,
    current_user_tenant: tuple[User, str] = Depends(require_roles_with_tenant("client_admin", "employee")),
    db: AsyncSession = Depends(get_db),
):
    _, tenant_id = current_user_tenant

    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == uuid.UUID(tenant_id)
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    file_path = get_document_file_path(
        uuid.UUID(tenant_id), document_id, document.stored_filename
    )

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found"
        )

    return FileResponse(
        path=file_path,
        filename=document.original_filename,
        media_type=document.mime_type,
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    current_user_tenant: tuple[User, str] = Depends(require_roles_with_tenant("client_admin")),
    db: AsyncSession = Depends(get_db),
):
    _, tenant_id = current_user_tenant

    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.tenant_id == uuid.UUID(tenant_id)
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )

    # Delete file from disk
    delete_document_file(
        uuid.UUID(tenant_id), document_id, document.stored_filename
    )

    # Delete from database
    await db.execute(
        delete(Document).where(
            Document.id == document_id,
            Document.tenant_id == uuid.UUID(tenant_id)
        )
    )
    await db.commit()