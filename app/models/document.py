import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import BigInteger, Enum, ForeignKey, Index, Text, DateTime, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


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


class Document(Base):
    __tablename__ = 'documents'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    stored_filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # VQ-202: approval workflow and document versions.
    #
    # A logical document is the set of rows sharing document_group_id. The first
    # upload generates the group; uploading a new version reuses it and increments
    # version_number. status is the approval state machine: only 'approved' takes
    # part in search, and uq_documents_one_approved_per_group guarantees at most
    # one approved version per group at the database level.
    status: Mapped[str] = mapped_column(
        Enum('pending', 'approved', 'archived', 'rejected', name='document_approval_status'),
        nullable=False,
        default='pending',
        server_default='pending',
    )
    document_group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, default=uuid.uuid4
    )
    version_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default='1'
    )
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey('documents.id', ondelete='SET NULL'), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # VQ-203: processing fields
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        ENUM(ProcessingStatus, name="processing_status", create_type=False),
        nullable=False,
        default=ProcessingStatus.queued,
    )
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    tenant: Mapped['Tenant'] = relationship('Tenant', back_populates='documents')
    uploader: Mapped['User'] = relationship('User', back_populates='documents', foreign_keys=[uploaded_by])
    chunks: Mapped[list['DocumentChunk']] = relationship('DocumentChunk', back_populates='document', cascade='all, delete-orphan')

    __table_args__ = (
        Index('ix_documents_tenant', 'tenant_id', 'created_at'),
        Index('ix_documents_tenant_status', 'tenant_id', 'status'),
        Index('ix_documents_group', 'document_group_id', 'version_number'),
    )


class DocumentJob(Base):
    __tablename__ = 'document_jobs'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('documents.id', ondelete='CASCADE'), nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        ENUM(JobStatus, name="job_status", create_type=False),
        nullable=False,
        default=JobStatus.queued,
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    document: Mapped[Document] = relationship('Document')

    __table_args__ = (
        Index('ix_document_jobs_tenant_status_created', 'tenant_id', 'status', 'created_at'),
        UniqueConstraint('document_id', 'payload', name='uq_document_jobs_document_payload'),
    )