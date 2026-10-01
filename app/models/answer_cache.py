import uuid
from datetime import datetime
from typing import List
from sqlalchemy import ForeignKey, UniqueConstraint, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class AnswerCache(Base):
    __tablename__ = "answer_cache"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(nullable=False)  # 'client_admin' | 'employee'
    question_hash: Mapped[str] = mapped_column(nullable=False)  # SHA-256 hex
    kb_version: Mapped[int] = mapped_column(nullable=False)
    answer_text: Mapped[str] = mapped_column(nullable=False)
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    source_chunk_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="answer_cache_entries")
    document = relationship("Document", back_populates="answer_cache_entries")

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "role",
            "question_hash",
            "kb_version",
            name="uq_answer_cache_tenant_role_qhash_kb",
        ),
    )