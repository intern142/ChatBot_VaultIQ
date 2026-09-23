import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, UUID, func
from sqlalchemy.orm import relationship
from app.database import Base


class Invite(Base):
    __tablename__ = "invites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    code = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())

    tenant = relationship("Tenant", back_populates="invites")

    def __repr__(self):
        return f"<Invite(id={self.id}, tenant_id={self.tenant_id}, email={self.email})>"