from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional, List, Dict, Any

from app.database import get_db
from app.auth.permissions import require_roles
from app.models.user import User
from app.schemas.admin import (
    TenantOverview,
    TenantOverviewDetail,
    PlatformHealth,
    PlatformStats,
)
from app.services.platform_stats import (
    get_all_tenants_overview,
    get_tenant_detail,
    get_platform_health,
    get_platform_stats,
)

router = APIRouter(prefix="/admin/platform", tags=["admin-platform"], dependencies=[Depends(require_roles("super_admin"))])


@router.get("/overview", response_model=List[TenantOverview])
async def get_platform_overview(
    db: AsyncSession = Depends(get_db),
):
    """
    Get overview statistics for all tenants.
    Super Admin only. Returns metadata only - no document content.
    """
    tenants = await get_all_tenants_overview(db)
    return tenants


@router.get("/overview/{tenant_id}", response_model=TenantOverviewDetail)
async def get_tenant_overview(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get detailed overview for a single tenant including time-series data.
    Super Admin only. Returns metadata only - no document content.
    """
    detail = await get_tenant_detail(db, str(tenant_id))
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return detail


@router.get("/health", response_model=PlatformHealth)
async def get_platform_health_endpoint(
    db: AsyncSession = Depends(get_db),
):
    """
    Get platform health metrics.
    Super Admin only. Returns DB, disk, processing queue, no-internet check, error rate.
    """
    health = await get_platform_health(db)
    return health


@router.get("/stats", response_model=PlatformStats)
async def get_platform_stats_endpoint(
    db: AsyncSession = Depends(get_db),
):
    """
    Get platform-wide aggregate statistics.
    Super Admin only. Returns totals across all tenants.
    """
    stats = await get_platform_stats(db)
    return stats