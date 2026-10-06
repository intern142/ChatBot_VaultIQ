from datetime import datetime
from typing import Literal, Optional
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
    # VQ-202: approval state and position in the version group.
    status: str
    document_group_id: uuid.UUID
    version_number: int
    supersedes_id: Optional[uuid.UUID] = None
    approved_by: Optional[uuid.UUID] = None
    approved_at: Optional[datetime] = None
    decision_note: Optional[str] = None
    # VQ-203: processing fields
    processing_status: ProcessingStatus
    processing_error: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    processing_version: int

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int
    page: int
    page_size: int


class ApprovalDecisionRequest(BaseModel):
    """Body for approve/reject. The note is optional per AC2."""

    note: Optional[str] = None


class VersionHistoryResponse(BaseModel):
    document_group_id: uuid.UUID
    versions: list[DocumentResponse]

    model_config = ConfigDict(from_attributes=True)


class SearchableDocumentsResponse(BaseModel):
    """The approved set only.

    This exists so VQ-202 can be proven end to end before the search engine lands
    in VQ-203. It is deliberately not a search: it returns whole documents with no
    ranking and no query. It answers exactly one question - which documents are
    currently approved and therefore eligible to answer something.
    """

    tenant_id: uuid.UUID
    knowledge_base_version: int
    documents: list[DocumentResponse]

    model_config = ConfigDict(from_attributes=True)


class StorageUsageResponse(BaseModel):
    tenant_id: uuid.UUID
    total_documents: int
    total_size_bytes: int
    total_size_mb: float