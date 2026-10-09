import os
import re
import uuid
import magic
from datetime import datetime, timezone
from PIL import Image
from io import BytesIO
from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.tenant_settings import TenantSettings
from app.models.tenant import Tenant
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.storage import (
    get_tenant_storage_path,
    save_uploaded_file,
    delete_document_file,
)
from io import BytesIO
from app.config import get_settings


settings = get_settings()

# Max logo size: 500KB
MAX_LOGO_SIZE = 500 * 1024
# Max logo dimensions
MAX_LOGO_DIMENSION = 512
# Allowed image MIME types
ALLOWED_IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp"}


class TenantSettingsService:
    """Service for managing tenant settings with validation."""

    @staticmethod
    def _validate_image(file_bytes: bytes, mime_type: str) -> tuple[bool, str]:
        """Validate image file: MIME, size, dimensions. Returns (is_valid, error_message)."""
        if mime_type not in ALLOWED_IMAGE_MIMES:
            return False, f"Unsupported image format: {mime_type}. Allowed: PNG, JPEG, WebP"

        if len(file_bytes) > MAX_LOGO_SIZE:
            return False, f"Image too large: {len(file_bytes)} bytes (max {MAX_LOGO_SIZE})"

        try:
            img = Image.open(BytesIO(file_bytes))
            width, height = img.size
            if width > MAX_LOGO_DIMENSION or height > MAX_LOGO_DIMENSION:
                return False, f"Image dimensions {width}x{height} exceed max {MAX_LOGO_DIMENSION}x{MAX_LOGO_DIMENSION}"
            # Verify it's a valid image
            img.verify()
        except Exception as e:
            return False, f"Invalid image file: {e}"

        return True, ""

    @staticmethod
    async def get_settings(db: AsyncSession, tenant_id: uuid.UUID) -> Optional[TenantSettings]:
        """Get tenant settings."""
        result = await db.execute(
            select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_public_settings(db: AsyncSession, short_code: str) -> Optional[Dict[str, Any]]:
        """Get public tenant info by short_code. Returns same structure for invalid codes."""
        result = await db.execute(
            select(Tenant).where(Tenant.short_code == short_code)
        )
        tenant = result.scalar_one_or_none()

        if tenant is None:
            return {"name": "", "logo_path": None, "accent_colour": None}

        settings_result = await db.execute(
            select(TenantSettings).where(TenantSettings.tenant_id == tenant.id)
        )
        ts = settings_result.scalar_one_or_none()

        return {
            "name": tenant.name,
            "logo_path": ts.logo_path if ts else None,
            "accent_colour": ts.accent_colour if ts else None,
        }

    @staticmethod
    async def update_settings(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        is_super_admin: bool,
        payload: Dict[str, Any],
        logo_file: Optional[bytes] = None,
        logo_filename: Optional[str] = None,
    ) -> TenantSettings:
        """Update tenant settings with validation."""
        # Get existing settings or create new
        result = await db.execute(
            select(TenantSettings).where(TenantSettings.tenant_id == tenant_id)
        )
        ts = result.scalar_one_or_none()

        if ts is None:
            ts = TenantSettings(tenant_id=tenant_id)
            db.add(ts)
            await db.flush()

        # Track changes for audit
        changes = {}

        # Update fields
        for field in ["display_name", "accent_colour", "not_found_message",
                      "allowed_upload_formats", "conversation_retention_days"]:
            if field in payload and payload[field] is not None:
                old_val = getattr(ts, field)
                new_val = payload[field]
                if old_val != new_val:
                    changes[field] = {"old": old_val, "new": new_val}
                    setattr(ts, field, new_val)

        # Handle logo upload
        if logo_file is not None and logo_filename is not None:
            # Detect MIME from content
            mime_type = magic.from_buffer(logo_file, mime=True)
            valid, error = TenantSettingsService._validate_image(logo_file, mime_type)
            if not valid:
                raise ValueError(error)

            # Determine extension
            ext = ".png" if mime_type == "image/png" else ".jpg" if mime_type == "image/jpeg" else ".webp"
            stored_name = f"logo{ext}"

            # Delete old logo if exists (storage/{tenant_id}/settings/logo.{ext})
            if ts.logo_path:
                try:
                    # Extract stored filename from path
                    old_filename = os.path.basename(ts.logo_path)
                    delete_document_file(tenant_id, uuid.UUID("00000000-0000-0000-0000-000000000000"), old_filename)
                except Exception:
                    pass  # Ignore deletion errors

            # Save new logo to tenant's settings storage
            # We use a special document_id for settings: all zeros
            settings_doc_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
            file_obj = BytesIO(logo_file)
            saved_path = save_uploaded_file(file_obj, tenant_id, settings_doc_id, stored_name)
            # Store relative path for portability
            rel_path = os.path.relpath(saved_path, get_tenant_storage_path(tenant_id))
            changes["logo_path"] = {"old": ts.logo_path, "new": rel_path}
            ts.logo_path = rel_path

        # Super admin only: storage_quota_mb (handled separately in tenant update)
        if is_super_admin and "storage_quota_mb" in payload:
            # This updates the tenant table, not settings
            tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
            tenant = tenant_result.scalar_one()
            if tenant and payload["storage_quota_mb"] is not None:
                old_val = tenant.storage_quota_mb
                new_val = payload["storage_quota_mb"]
                if old_val != new_val:
                    changes["storage_quota_mb"] = {"old": old_val, "new": new_val}
                    tenant.storage_quota_mb = new_val

        ts.updated_by = user_id
        ts.updated_at = datetime.now(timezone.utc)

        await db.flush()

        # Write audit log
        if changes:
            audit = AuditLog(
                tenant_id=tenant_id,
                actor_user_id=user_id,
                actor_role="super_admin" if is_super_admin else "client_admin",
                action="update_tenant_settings",
                target_type="tenant",
                target_id=tenant_id,
                details=changes,
            )
            db.add(audit)

        await db.commit()
        await db.refresh(ts)
        return ts

    @staticmethod
    async def get_system_allowed_formats() -> List[str]:
        """Return system-wide allowed formats."""
        return SYSTEM_ALLOWED_FORMATS.copy()