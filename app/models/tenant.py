import uuid
from datetime import datetime, timezone
from typing import List
from sqlalchemy import String, DateTime, Enum, Integer, func
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

    def __repr__(self):
        return f"<Tenant(id={self.id}, short_code={self.short_code}, name={self.name})>"