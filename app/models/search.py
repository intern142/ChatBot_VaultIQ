import uuid
from datetime import datetime, timezone
from sqlalchemy import BigInteger, ForeignKey, Index, Integer, Text, DateTime, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from app.models.base import Base


class DocumentChunk(Base):
    __tablename__ = 'document_chunks'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('documents.id', ondelete='CASCADE'), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_tsv: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="",
        comment="tsvector generated from content"
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    document: Mapped['Document'] = relationship('Document', back_populates='chunks')

    __table_args__ = (
        PrimaryKeyConstraint('tenant_id', 'id', name='pk_document_chunks'),
        Index('ix_document_chunks_tenant_doc', 'tenant_id', 'document_id'),
    )


class IndexingJob(Base):
    __tablename__ = 'indexing_jobs'

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey('documents.id', ondelete='CASCADE'), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default='pending')
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default='0')
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('ix_indexing_jobs_tenant_status', 'tenant_id', 'status'),
        Index('ix_indexing_jobs_document', 'document_id'),
    )