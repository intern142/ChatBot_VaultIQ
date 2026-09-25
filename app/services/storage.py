import uuid
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


class UploadTooLargeError(ValueError):
    pass


def save_uploaded_file(
    file: BinaryIO,
    tenant_id: uuid.UUID,
    document_id: uuid.UUID,
    stored_filename: str,
    max_bytes: int | None = None
) -> Path:
    dest_dir = ensure_storage_dirs(tenant_id, document_id)
    dest_path = dest_dir / stored_filename
    written = 0
    try:
        with open(dest_path, "wb") as destination:
            while chunk := file.read(1024 * 1024):
                written += len(chunk)
                if max_bytes is not None and written > max_bytes:
                    raise UploadTooLargeError
                destination.write(chunk)
    except Exception:
        dest_path.unlink(missing_ok=True)
        tenant_dir = get_tenant_storage_path(tenant_id)
        for directory in (dest_dir, dest_dir.parent, tenant_dir):
            if directory.exists() and not any(directory.iterdir()):
                directory.rmdir()
        raise
    return dest_path


def delete_document_file(tenant_id: uuid.UUID, document_id: uuid.UUID, stored_filename: str) -> bool:
    file_path = get_document_file_path(tenant_id, document_id, stored_filename)
    if file_path.exists():
        file_path.unlink()
        doc_dir = get_document_storage_path(tenant_id, document_id)
        tenant_dir = get_tenant_storage_path(tenant_id)
        for directory in (doc_dir, doc_dir.parent, tenant_dir):
            if directory.exists() and not any(directory.iterdir()):
                directory.rmdir()
        return True
    return False


def get_file_size(tenant_id: uuid.UUID, document_id: uuid.UUID, stored_filename: str) -> int:
    file_path = get_document_file_path(tenant_id, document_id, stored_filename)
    return file_path.stat().st_size if file_path.exists() else 0