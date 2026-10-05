import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, Text, false
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


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
    category: Mapped[str] = mapped_column(
        Enum('policy', 'hr', 'sop', 'process', 'other', name='document_category'),
        nullable=False,
        default='other'
    )
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    extraction_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    extraction_page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_truncated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
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
    supersedes_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('documents.id', ondelete='SET NULL'), nullable=True
    )
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decision_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tenant: Mapped['Tenant'] = relationship('Tenant', back_populates='documents')
    # documents.uploaded_by and documents.approved_by both reference users.id
    # (VQ-202), so the path has to be named explicitly.
    uploader: Mapped['User'] = relationship(
        'User', back_populates='documents', foreign_keys=[uploaded_by]
    )
    chunks: Mapped[list['DocumentChunk']] = relationship(
        'DocumentChunk', back_populates='document', cascade='all, delete-orphan'
    )

    __table_args__ = (
        Index('ix_documents_tenant', 'tenant_id', 'created_at'),
        Index('ix_documents_tenant_status', 'tenant_id', 'status'),
        Index('ix_documents_group', 'document_group_id', 'version_number'),
    )
