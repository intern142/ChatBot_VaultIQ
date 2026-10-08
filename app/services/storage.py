import os
import uuid
import shutil
from pathlib import Path
from typing import BinaryIO
from app.config import get_settings

settings = get_settings()

STORAGE_ROOT = Path(settings.STORAGE_ROOT)


def get_tenant_storage_path(tenant_id: uuid.UUID) -> Path:
    return STORAGE_ROOT / str(tenant_id)


def get_document_storage_path(tenant_id: uuid.UUID, document_id: uuid.UUID) -> Path:
    return get_tenant_storage_path(tenant_id) / str(document_id) / "original"


def get_document_file_path(tenant_id: uuid.UUID, document_id: uuid.UUID, stored_filename: str) -> Path:
    return get_document_storage_path(tenant_id, document_id) / stored_filename


def ensure_storage_dirs(tenant_id: uuid.UUID, document_id: uuid.UUID) -> Path:
    path = get_document_storage_path(tenant_id, document_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_uploaded_file(
    file: BinaryIO,
    tenant_id: uuid.UUID,
    document_id: uuid.UUID,
    stored_filename: str
) -> Path:
    dest_dir = ensure_storage_dirs(tenant_id, document_id)
    dest_path = dest_dir / stored_filename
    with open(dest_path, "wb") as f:
        shutil.copyfileobj(file, f)
    return dest_path


def delete_document_file(tenant_id: uuid.UUID, document_id: uuid.UUID, stored_filename: str) -> bool:
    file_path = get_document_file_path(tenant_id, document_id, stored_filename)
    if file_path.exists():
        file_path.unlink()
        # Clean up empty directories
        doc_dir = get_document_storage_path(tenant_id, document_id)
        if doc_dir.exists() and not any(doc_dir.iterdir()):
            doc_dir.rmdir()
        tenant_dir = get_tenant_storage_path(tenant_id)
        if tenant_dir.exists() and not any(tenant_dir.iterdir()):
            tenant_dir.rmdir()
        return True
    return False


def get_file_size(tenant_id: uuid.UUID, document_id: uuid.UUID, stored_filename: str) -> int:
    file_path = get_document_file_path(tenant_id, document_id, stored_filename)
    return file_path.stat().st_size if file_path.exists() else 0


def purge_tenant_storage(tenant_id: uuid.UUID) -> dict:
    """VQ-403: Remove the tenant's entire storage directory.

    Idempotent: a missing directory returns zero counts. Returns the number
    of files and bytes that existed on disk immediately before removal.
    """
    tenant_dir = get_tenant_storage_path(tenant_id)
    if not tenant_dir.exists():
        return {"files_deleted": 0, "bytes_deleted": 0}

    files_deleted = 0
    bytes_deleted = 0
    for path in tenant_dir.rglob("*"):
        if path.is_file():
            files_deleted += 1
            bytes_deleted += path.stat().st_size

    shutil.rmtree(tenant_dir)
    return {"files_deleted": files_deleted, "bytes_deleted": bytes_deleted}