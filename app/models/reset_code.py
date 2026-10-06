from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ResetCode(Base):
    """A one-time password-reset credential issued by a Client Admin.

    The plaintext code exists only in the HTTP response. `code_hash` holds its
    SHA-256 digest, so a database read cannot yield a usable credential.

    `tenant_id` is denormalised from the target user rather than joined at
    consume time: the consuming endpoint is unauthenticated, so it has no tenant
    context and cannot read `users` to discover one. See migration
    27905f137fd4 for the full reasoning.
    """

    __tablename__ = "reset_codes"
    __table_args__ = (
        Index("ix_reset_codes_user_live", "user_id", "used_at", "expires_at"),
    )

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default="gen_random_uuid()",
    )
    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    issuer: Mapped["User"] = relationship("User", foreign_keys=[created_by])
