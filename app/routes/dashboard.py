from fastapi import APIRouter, Depends, HTTPException, Response, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from app.database import get_db
from app.auth.permissions import require_roles_with_tenant
from app.models.user import User
from typing import Optional

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview")
async def get_overview(
    current_user: User = Depends(require_roles_with_tenant("client_admin")),
    db: AsyncSession = Depends(get_db),
):
    return {
        "questions_per_day_30d": [],
        "active_users": 0,
        "answered_count": 0,
        "partial_count": 0,
        "not_found_count": 0,
        "avg_confidence": None,
    }


@router.get("/overview/30d")
async def get_overview_30d(
    current_user: User = Depends(require_roles_with_tenant("client_admin")),
    db: AsyncSession = Depends(get_db),
):
    return {
        "questions_per_day_30d": [],
        "active_users": 0,
        "answered_count": 0,
        "partial_count": 0,
        "not_found_count": 0,
        "avg_confidence": None,
    }


@router.get("/documents")
async def get_documents(
    current_user: User = Depends(require_roles_with_tenant("client_admin")),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
):
    return {"items": [], "total": 0, "limit": limit, "offset": offset}


@router.get("/users")
async def get_users(
    current_user: User = Depends(require_roles_with_tenant("client_admin")),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
):
    return {"items": [], "total": 0, "limit": limit, "offset": offset}


@router.get("/audit")
async def get_audit(
    current_user: User = Depends(require_roles_with_tenant("client_admin")),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
):
    return {"items": [], "total": 0, "limit": limit, "offset": offset}


@router.get("/feedback")
async def get_feedback(
    current_user: User = Depends(require_roles_with_tenant("client_admin")),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
):
    return {"items": [], "total": 0, "limit": limit, "offset": offset}


@router.get("/knowledge-gaps")
async def get_knowledge_gaps(
    current_user: User = Depends(require_roles_with_tenant("client_admin")),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    return {"items": [], "total": 0, "limit": limit, "offset": offset}


def _csv_escape_cell(val: Any) -> str:
    if val is None:
        return ""
    s = str(val)
    if s and s[0] in ("+", "-", "=", "@", "\t", "\r"):
        s = "'" + s
    if '"' in s:
        s = s.replace('"', '""')
    return s


@router.get("/export/{entity}")
async def export_entity(
    entity: str,
    current_user: User = Depends(require_roles_with_tenant("client_admin")),
    db: AsyncSession = Depends(get_db),
):
    if entity not in ("documents", "users", "audit", "feedback"):
        raise HTTPException(status_code=404, detail="Not found")
    content = '"header1","header2"\n'
    return Response(content=content, media_type="text/csv", headers={
        "Content-Disposition": f"attachment; filename={entity}.csv"
    })
