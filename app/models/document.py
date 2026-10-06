import uuid
from datetime import datetime, timezone
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

    tenant: Mapped['Tenant'] = relationship('Tenant', back_populates='documents')
    uploader: Mapped['User'] = relationship('User', back_populates='documents')

    __table_args__ = (
        Index('ix_documents_tenant', 'tenant_id', 'created_at'),
    )