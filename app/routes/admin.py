"""VQ-107: Admin endpoints for tenant lifecycle management."""
import secrets
import base64
from datetime import datetime, timezone, timedelta
from uuid import UUID
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, set_tenant_context
from app.auth.dependencies import get_current_user
from app.auth.permissions import require_roles
from app.models.tenant import Tenant, TenantStatus
from app.models.user import User
from app.models.session import Session
from app.models.invite import Invite
from app.models.audit_log import AuditLog
from app.schemas.tenant import (
    TenantCreate,
    TenantResponse,
    TenantListResponse,
    InviteCreate,
    InviteResponse,
    AuditLogResponse,
)
from app.config import get_settings

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_roles("super_admin"))])
settings = get_settings()


def generate_invite_code() -> str:
    """Generate a cryptographically secure invite code (32 bytes → 43 char base64url)."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")


async def write_audit_log(
    db: AsyncSession,
    tenant_id: UUID,
    actor_user_id: Optional[UUID],
    actor_role: str,
    action: str,
    target_type: str,
    target_id: UUID,
    details: dict[str, Any],
) -> AuditLog:
    """Write an audit log entry. Caller must set tenant context."""
    audit = AuditLog(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )
    db.add(audit)
    await db.flush()
    return audit


@router.post("/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    request: TenantCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new tenant."""
    tenant = Tenant(
        short_code=request.short_code.upper(),
        name=request.name,
        storage_quota_mb=request.storage_quota_mb,
        status=TenantStatus.active,
    )
    db.add(tenant)
    await db.flush()

    await write_audit_log(
        db=db,
        tenant_id=tenant.id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        action="create_tenant",
        target_type="tenant",
        target_id=tenant.id,
        details={
            "short_code": tenant.short_code,
            "name": tenant.name,
            "storage_quota_mb": tenant.storage_quota_mb,
        },
    )

    await db.commit()
    await db.refresh(tenant)
    return tenant


@router.get("/tenants", response_model=list[TenantListResponse])
async def list_tenants(
    db: AsyncSession = Depends(get_db),
):
    """List all tenants (super_admin sees all, no RLS filter)."""
    result = await db.execute(select(Tenant).order_by(Tenant.created_at.desc()))
    tenants = result.scalars().all()
    return tenants


@router.patch("/tenants/{tenant_id}/suspend", response_model=TenantResponse)
async def suspend_tenant(
    tenant_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Suspend a tenant: revoke all sessions and set status to suspended."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    if tenant.status == TenantStatus.suspended:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant already suspended")

    if tenant.status == TenantStatus.offboarding:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot suspend offboarding tenant")

    if tenant.status == TenantStatus.purged:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot suspend purged tenant")

    # Revoke all sessions for this tenant
    await db.execute(
        delete(Session).where(Session.tenant_id == tenant_id)
    )

    tenant.status = TenantStatus.suspended
    await db.flush()

    await write_audit_log(
        db=db,
        tenant_id=tenant.id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        action="suspend_tenant",
        target_type="tenant",
        target_id=tenant.id,
        details={},
    )

    await db.commit()
    await db.refresh(tenant)
    return tenant


@router.patch("/tenants/{tenant_id}/reactivate", response_model=TenantResponse)
async def reactivate_tenant(
    tenant_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reactivate a suspended tenant."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    if tenant.status != TenantStatus.suspended:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant is not suspended")

    tenant.status = TenantStatus.active
    await db.flush()

    await write_audit_log(
        db=db,
        tenant_id=tenant.id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        action="reactivate_tenant",
        target_type="tenant",
        target_id=tenant.id,
        details={},
    )

    await db.commit()
    await db.refresh(tenant)
    return tenant


@router.post("/tenants/{tenant_id}/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def create_invite(
    tenant_id: UUID,
    request: InviteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an invite for the first Client Admin of a tenant."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    if tenant.status != TenantStatus.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can only invite for active tenants")

    # Check if tenant already has a client_admin
    result = await db.execute(
        select(User).where(User.tenant_id == tenant_id, User.role == "client_admin")
    )
    existing_admin = result.scalar_one_or_none()
    if existing_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant already has a Client Admin")

    # Check for existing unused invite for this email
    result = await db.execute(
        select(Invite).where(
            Invite.tenant_id == tenant_id,
            Invite.email == request.email,
            Invite.used_at.is_(None),
            Invite.expires_at > datetime.now(timezone.utc),
        )
    )
    existing_invite = result.scalar_one_or_none()
    if existing_invite:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Active invite already exists for this email")

    expires_at = datetime.now(timezone.utc) + timedelta(hours=request.expires_in_hours)
    code = generate_invite_code()

    invite = Invite(
        tenant_id=tenant_id,
        email=request.email,
        code=code,
        expires_at=expires_at,
        created_by=current_user.id,
    )
    db.add(invite)
    await db.flush()

    await write_audit_log(
        db=db,
        tenant_id=tenant.id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        action="create_invite",
        target_type="invite",
        target_id=invite.id,
        details={
            "email": invite.email,
            "expires_at": invite.expires_at.isoformat(),
        },
    )

    await db.commit()
    await db.refresh(invite)
    return invite


@router.get("/tenants/{tenant_id}/audit", response_model=list[AuditLogResponse])
async def get_audit_log(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get audit log for a tenant."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    # Set tenant context for RLS
    await set_tenant_context(db, str(tenant_id))

    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.created_at.desc())
        .limit(500)
    )
    logs = result.scalars().all()
    return logs