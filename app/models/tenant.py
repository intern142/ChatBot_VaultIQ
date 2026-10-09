import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import String, DateTime, Enum, Integer, func, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    short_code: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("active", "suspended", "offboarding", "purged", name="tenant_status"),
        nullable=False,
        default="active",
    )
    storage_quota_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=2048)
    # VQ-202: bumped whenever this tenant's approved set changes, so cached answers
    # can be invalidated without rescanning the corpus. Bumped on approve only -
    # rejecting a pending version leaves the approved set untouched.
    knowledge_base_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=365)
    # VQ-403: offboarding grace window (active/suspended -> offboarding -> purged)
    offboarded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    offboarded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    purge_after: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    purged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    documents: Mapped[List['Document']] = relationship(
        'Document', back_populates='tenant', lazy='dynamic'
    )
    invites: Mapped[List['Invite']] = relationship(
        'Invite', back_populates='tenant', cascade="all, delete-orphan"
    )
    audit_logs: Mapped[List['AuditLog']] = relationship(
        'AuditLog', back_populates='tenant', cascade="all, delete-orphan"
    )
    settings: Mapped[Optional['TenantSettings']] = relationship(
        'TenantSettings', back_populates='tenant', cascade="all, delete-orphan", uselist=False
    )
    answer_cache_entries: Mapped[List['AnswerCache']] = relationship(
        'AnswerCache', back_populates='tenant', cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Tenant(id={self.id}, short_code={self.short_code}, name={self.name})>"