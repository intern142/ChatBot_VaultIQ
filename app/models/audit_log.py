import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, UUID, JSON, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    actor_role = Column(String(50), nullable=False)
    action = Column(String(100), nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    details = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    tenant = relationship("Tenant", back_populates="audit_logs")
    actor = relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog(id={self.id}, tenant_id={self.tenant_id}, action={self.action}, target_type={self.target_type}, target_id={self.target_id})>"