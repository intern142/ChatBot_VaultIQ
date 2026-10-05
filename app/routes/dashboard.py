from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from app.database import get_db
from app.auth.dependencies import get_current_user_with_tenant
from app.auth.permissions import require_roles_with_tenant
from app.models.user import User
from typing import Optional

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Basic skeleton - will expand
@router.get("/overview")
async def get_overview(
    current_user: User = Depends(require_roles_with_tenant("client_admin")),
    db: AsyncSession = Depends(get_db),
):
    return {"questions_per_day_30d": [], "active_users": 0, "answered_count": 0, "partial_count": 0, "not_found_count": 0, "avg_confidence": None}
