import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_user_email_per_tenant"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        Enum("super_admin", "client_admin", "employee", name="user_role"),
        nullable=False,
    )
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # VQ-301 AC3. A boolean rather than a status enum: a user is active or it is
    # not, and "pending invite" is a row in `invites`, not a state of a user.
    # NOT NULL, so there is no third state to interpret. The server default of
    # true (migration c4d81f0a7e26) matches this Python default on purpose: a row
    # written without the flag is an active user, which is what it meant before
    # the column existed. `true` is also the safe direction - a path that forgets
    # the flag reproduces existing behaviour rather than disabling an account.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # documents.uploaded_by and documents.approved_by both reference users.id
    # (VQ-202), so the path has to be named explicitly.
    documents: Mapped[List['Document']] = relationship(
        'Document',
        back_populates='uploader',
        foreign_keys='Document.uploaded_by',
        lazy='dynamic',
    )
    sessions: Mapped[List['Session']] = relationship(
        'Session', back_populates='user', lazy='dynamic'
    )
    audit_logs: Mapped[List['AuditLog']] = relationship(
        'AuditLog', back_populates='actor', cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"