import uuid
from datetime import datetime
from sqlalchemy import Boolean, Column, String, DateTime, Enum, ForeignKey, func, UniqueConstraint, Integer
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
    failed_login_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    # VQ-301 AC3. A boolean rather than a status enum: a user is active or it is
    # not, and "pending invite" is a row in `invites`, not a state of a user.
    # NOT NULL, so there is no third state to interpret. The server default of
    # true (migration c4d81f0a7e26) matches this Python default on purpose: a row
    # written without the flag is an active user, which is what it meant before
    # the column existed. `true` is also the safe direction - a path that forgets
    # the flag reproduces existing behaviour rather than disabling an account.
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now()
    )

    documents = relationship("Document", back_populates="uploader", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="actor", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
