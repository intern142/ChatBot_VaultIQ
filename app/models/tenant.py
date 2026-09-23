import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    short_code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    status = Column(
        Enum("active", "suspended", "offboarding", "purged", name="tenant_status"),
        nullable=False,
        default="active",
    )
    storage_quota_mb = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now()
    )

    documents = relationship("Document", back_populates="tenant", cascade="all, delete-orphan")
    invites = relationship("Invite", back_populates="tenant", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="tenant", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tenant(id={self.id}, short_code={self.short_code}, name={self.name})>"
