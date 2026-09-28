from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
import uuid
import enum


class ProcessingStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class JobStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    done = "done"
    failed = "failed"


class JobResponse(BaseModel):
    id: uuid.UUID
    status: JobStatus
    retry_count: int
    max_retries: int
    last_error: Optional[str] = None
    payload: dict
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ProcessingStatusResponse(BaseModel):
    document_id: uuid.UUID
    processing_status: ProcessingStatus
    processing_error: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    processing_version: int
    job: Optional[JobResponse] = None

    model_config = ConfigDict(from_attributes=True)


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