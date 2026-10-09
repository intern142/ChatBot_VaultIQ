from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
import uuid


class DocumentBase(BaseModel):
    original_filename: str
    mime_type: str
    size_bytes: int


class DocumentCreate(DocumentBase):
    pass


class DocumentResponse(DocumentBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    stored_filename: str
    uploaded_by: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int
    page: int
    page_size: int


class StorageUsageResponse(BaseModel):
    tenant_id: uuid.UUID
    total_documents: int
    total_size_bytes: int
    total_size_mb: float


class BulkFileResult(BaseModel):
    """Outcome for one file in a bulk upload."""

    filename: str
    success: bool
    document: Optional[DocumentResponse] = None
    error: Optional[str] = None


class BulkUploadResponse(BaseModel):
    """Summary of a multi-file upload.

    Each file is handled independently: a file that fails validation or storage
    is reported in `results` with `success=False` and an `error`, while the rest
    of the batch is still uploaded. The endpoint returns 200 once the batch has
    been processed.
    """

    processed: int
    created: int
    failed: int
    results: list[BulkFileResult]