"""VQ-304: Public endpoints for tenant lookup."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.tenant import Tenant
from app.schemas.tenant_settings import TenantPublicResponse
from app.services.tenant_settings import TenantSettingsService

router = APIRouter(prefix="/tenants", tags=["public"])


@router.get("/{short_code}/public", response_model=TenantPublicResponse)
async def get_tenant_public(
    short_code: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Public tenant lookup by organisation code.
    Returns only name, logo, and colour.
    Behaves identically for non-existent codes (no existence leak).
    """
    # Normalize code
    code = short_code.strip().upper()

    result = await TenantSettingsService.get_public_settings(db, code)

    # Always return 200 with same structure - no existence leak
    return TenantPublicResponse(**result)