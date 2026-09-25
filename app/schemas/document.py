from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict
import uuid


class DocumentBase(BaseModel):
    original_filename: str
    mime_type: str
    size_bytes: int
    category: Literal['policy', 'hr', 'sop', 'process', 'other']


class DocumentCreate(DocumentBase):
    pass


class DocumentResponse(DocumentBase):
    id: uuid.UUID
    tenant_id: uuid.UUID
    stored_filename: str
    uploaded_by: uuid.UUID
    extraction_method: Literal['pdf_text', 'ocr', 'none'] | None = None
    extraction_status: Literal['completed', 'no_text', 'unavailable', 'not_required'] | None = None
    extraction_page_count: int | None = None
    extraction_truncated: bool
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