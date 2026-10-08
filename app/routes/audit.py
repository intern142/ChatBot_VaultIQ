"""VQ-402: Client Admin compliance export of their own tenant's audit trail.

Tenant comes only from the verified token — no tenant id in path or query, so
there is no cross-tenant parameter to tamper with. The export request itself is
written to the trail first, so the returned file is self-including and the
request is recorded even if generation fails afterwards.
"""
import csv
import io
import json
import uuid
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import require_roles_with_tenant
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.tenant import Tenant
from app.models.user import User
from app.services.audit import write_audit_log

router = APIRouter(prefix="/audit", tags=["audit"])

CSV_COLUMNS = [
    "id",
    "created_at",
    "actor_user_id",
    "actor_role",
    "action",
    "target_type",
    "target_id",
    "details",
    "tenant_id",
]


def _row_dict(entry: AuditLog) -> dict:
    return {
        "id": str(entry.id),
        "created_at": entry.created_at.isoformat(),
        "actor_user_id": str(entry.actor_user_id) if entry.actor_user_id else "",
        "actor_role": entry.actor_role,
        "action": entry.action,
        "target_type": entry.target_type,
        "target_id": str(entry.target_id),
        "details": json.dumps(entry.details, sort_keys=True),
        "tenant_id": str(entry.tenant_id),
    }


@router.get("/export")
async def export_audit_trail(
    start_date: date | None = Query(None, description="Inclusive lower bound (UTC)"),
    end_date: date | None = Query(None, description="Inclusive upper bound (UTC)"),
    format: str = Query("csv", pattern="^(csv|json)$"),
    current_user_tenant: tuple[User, str] = Depends(
        require_roles_with_tenant("client_admin")
    ),
    db: AsyncSession = Depends(get_db),
):
    """Export this tenant's audit trail for a date range (CSV or JSON)."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be on or before end_date",
        )

    current_user, tenant_id = current_user_tenant
    tenant_uuid = uuid.UUID(tenant_id)

    # The export itself is recorded before any row is read.
    await write_audit_log(
        db=db,
        tenant_id=tenant_uuid,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        action="export_audit",
        target_type="audit_export",
        target_id=tenant_uuid,
        details={
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "format": format,
        },
    )

    stmt = (
        select(AuditLog)
        .where(AuditLog.tenant_id == tenant_uuid)
        .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
    )
    if start_date:
        stmt = stmt.where(
            AuditLog.created_at
            >= datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        )
    if end_date:
        stmt = stmt.where(
            AuditLog.created_at
            < datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=timezone.utc)
        )

    entries = (await db.execute(stmt)).scalars().all()

    tenant_result = await db.execute(
        select(Tenant.short_code).where(Tenant.id == tenant_uuid)
    )
    short_code = (tenant_result.scalar_one_or_none() or "tenant").upper()
    await db.commit()

    date_part = f"{start_date.isoformat() if start_date else 'all'}_{end_date.isoformat() if end_date else 'all'}"
    filename = f"audit_export_{short_code}_{date_part}.{format}"

    if format == "json":
        return Response(
            content=json.dumps([_row_dict(e) for e in entries], indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, lineterminator="\r\n")
    writer.writeheader()
    for entry in entries:
        writer.writerow(_row_dict(entry))
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
