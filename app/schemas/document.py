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