import uuid
import mimetypes
from typing import BinaryIO
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Query
from fastapi.responses import FileResponse
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth.dependencies import get_current_user_with_tenant
from app.auth.permissions import require_roles_with_tenant
from app.models.document import Document
from app.models.user import User
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

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv",
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def validate_file(file: UploadFile) -> None:
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {MAX_FILE_SIZE // (1024*1024)}MB"
        )

    mime_type = file.content_type
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_MIME_TYPES))}"
        )


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user_tenant: tuple[User, str] = Depends(require_roles_with_tenant("client_admin", "employee")),
    db: AsyncSession = Depends(get_db),
):
    current_user, tenant_id = current_user_tenant

    validate_file(file)

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required"
        )

    document_id = uuid.uuid4()
    stored_filename = f"{document_id}{mimetypes.guess_extension(file.content_type) or '.bin'}"

    # Save file to disk
    file_path = save_uploaded_file(
        file.file,
        uuid.UUID(tenant_id),
        document_id,
        stored_filename
    )

    # Get actual size
    actual_size = file_path.stat().st_size

    # Create document record
    document = Document(
        id=document_id,
        tenant_id=uuid.UUID(tenant_id),
        original_filename=file.filename,
        stored_filename=stored_filename,
        mime_type=file.content_type or "application/octet-stream",
        size_bytes=actual_size,
        uploaded_by=current_user.id,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

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

    # For text files, return inline preview
    if document.mime_type.startswith("text/"):
        content = file_path.read_text(encoding="utf-8", errors="replace")
        preview_chars = 5000
        return {
            "document_id": str(document.id),
            "filename": document.original_filename,
            "mime_type": document.mime_type,
            "preview": content[:preview_chars],
            "truncated": len(content) > preview_chars,
        }

    # For other types, return file info
    return {
        "document_id": str(document.id),
        "filename": document.original_filename,
        "mime_type": document.mime_type,
        "size_bytes": document.size_bytes,
        "preview": None,
        "message": "Preview not available for this file type"
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