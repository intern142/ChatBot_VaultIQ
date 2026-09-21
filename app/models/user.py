import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, func, UniqueConstraint, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_user_email_per_tenant"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
    )
    email = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(
        Enum("super_admin", "client_admin", "employee", name="user_role"),
        nullable=False,
    )
    is_active = Column(Boolean, nullable=False, default=True)
    manager_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now()
    )

    manager = relationship("User", remote_side=[id], backref="subordinates")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role}, is_active={self.is_active})>"
