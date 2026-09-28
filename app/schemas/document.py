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
    # VQ-202: approval state and position in the version group.
    status: str
    document_group_id: uuid.UUID
    version_number: int
    supersedes_id: Optional[uuid.UUID] = None
    approved_by: Optional[uuid.UUID] = None
    approved_at: Optional[datetime] = None
    decision_note: Optional[str] = None

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