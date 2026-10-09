"""VQ-304: Client Admin endpoints for tenant settings."""
import magic
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, set_tenant_context
from app.auth.dependencies import get_current_user
from app.auth.permissions import require_roles
from app.models.tenant import Tenant
from app.schemas.tenant_settings import (
    TenantSettingsResponse,
    TenantSettingsUpdateClientAdmin,
    LogoUploadResponse,
)
from app.services.tenant_settings import TenantSettingsService

router = APIRouter(
    prefix="/tenant",
    tags=["tenant"],
    dependencies=[Depends(require_roles("client_admin"))]
)


@router.get("/settings", response_model=TenantSettingsResponse)
async def get_my_tenant_settings(
    current_user: "User" = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current tenant's settings (client_admin)."""
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenant context")

    ts = await TenantSettingsService.get_settings(db, tenant_id)
    if not ts:
        # Return defaults
        result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one()
        return TenantSettingsResponse(
            tenant_id=tenant_id,
            display_name=None,
            logo_path=None,
            accent_colour=None,
            not_found_message=None,
            allowed_upload_formats=None,
            conversation_retention_days=None,
            updated_by=None,
            updated_at=tenant.created_at,
        )
    return ts


@router.patch("/settings", response_model=TenantSettingsResponse)
async def update_my_tenant_settings(
    request: TenantSettingsUpdateClientAdmin,
    current_user: "User" = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current tenant's settings (client_admin - no storage_quota_mb)."""
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenant context")

    await set_tenant_context(db, str(tenant_id))

    payload = request.model_dump(exclude_unset=True)
    ts = await TenantSettingsService.update_settings(
        db=db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        is_super_admin=False,
        payload=payload,
    )
    return ts


@router.post("/settings/logo", response_model=LogoUploadResponse)
async def upload_my_tenant_logo(
    file: bytes = File(...),
    filename: str = "logo.png",
    current_user: "User" = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload current tenant's logo (client_admin)."""
    tenant_id = current_user.tenant_id
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenant context")

    await set_tenant_context(db, str(tenant_id))

    ts = await TenantSettingsService.update_settings(
        db=db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        is_super_admin=False,
        payload={},
        logo_file=file,
        logo_filename=filename,
    )
    return LogoUploadResponse(
        path=ts.logo_path,
        size_bytes=len(file),
        mime_type=magic.from_buffer(file, mime=True),
    )