import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import ForeignKey, String, Text, Integer, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class TenantSettings(Base):
    __tablename__ = "tenant_settings"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    logo_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    accent_colour: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)  # #RRGGBB or #RGB
    not_found_message: Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    allowed_upload_formats: Mapped[Optional[List[str]]] = mapped_column(JSONB(), nullable=True)
    conversation_retention_days: Mapped[Optional[int]] = mapped_column(Integer(), nullable=True)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="settings")
    updater = relationship("User")

    def __repr__(self):
        return f"<TenantSettings(tenant_id={self.tenant_id}, display_name={self.display_name})>"