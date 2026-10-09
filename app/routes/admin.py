"""VQ-107: Admin endpoints for tenant lifecycle management."""
import secrets
import base64
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, File
from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession

import magic

from sqlalchemy.exc import IntegrityError

from app.database import get_db, set_tenant_context
from app.auth.dependencies import get_current_user
from app.auth.password import verify_password
from app.auth.permissions import require_roles
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.tenant import TenantStatus
from app.models.session import Session
from app.models.invite import Invite
from app.models.audit_log import AuditLog
from app.services.audit import write_audit_log as shared_write_audit_log
from app.models.deletion_report import DeletionReport
from app.schemas.tenant import (
    TenantCreate,
    TenantResponse,
    TenantListResponse,
    TenantOffboardRequest,
    InviteCreate,
    InviteResponse,
    AuditLogResponse,
    DeletionReportResponse,
)
from app.schemas.tenant_settings import (
    TenantSettingsResponse,
    TenantSettingsUpdateSuperAdmin,
    LogoUploadResponse,
)
from app.services.tenant_settings import TenantSettingsService
from app.config import get_settings
from app.services.audit import write_audit_log

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_roles("super_admin"))])
settings = get_settings()

# VQ-403: fixed grace period between offboard and purge (no config column)
OFFBOARD_GRACE_DAYS = 7


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
    """Write an audit log entry. Caller must set tenant context.

    VQ-301 moved the body to app/services/audit.py so that admin.py and users.py
    share one implementation rather than two that can drift apart. This wrapper
    exists so VQ-107's four call sites and its tests are untouched; it narrows
    `target_id` to the non-optional type the /admin operations always pass.
    """
    return await shared_write_audit_log(
        db=db,
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )


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
        retention_days=request.retention_days,
        status=TenantStatus.active,
    )
    db.add(tenant)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tenant short code already exists",
        )

    # Create search index partition for this tenant
    partition_name = f"document_chunks_tenant_{str(tenant.id).replace('-', '_')}"
    await db.execute(
        text(f"""
            CREATE TABLE IF NOT EXISTS {partition_name} 
            PARTITION OF document_chunks 
            FOR VALUES IN ('{tenant.id}')
        """)
    )

    # Set tenant context so the audit entry passes RLS even under vaultiq_app
    await set_tenant_context(db, str(tenant.id))

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
            "retention_days": tenant.retention_days,
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

    # Set tenant context so session revocation and audit entry pass RLS
    await set_tenant_context(db, str(tenant_id))

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

    # Set tenant context so the audit entry passes RLS
    await set_tenant_context(db, str(tenant_id))

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


@router.patch("/tenants/{tenant_id}/offboard", response_model=TenantResponse)
async def offboard_tenant(
    tenant_id: UUID,
    request: TenantOffboardRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """VQ-403: Offboard a tenant after re-confirming the super admin's identity.

    Locks the tenant immediately (login and the request dependency already
    refuse offboarding tenants), revokes all its sessions, and starts the
    7-day grace window (purge_after).
    """
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    if tenant.status == TenantStatus.purged:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tenant is already purged")

    if tenant.status == TenantStatus.offboarding:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tenant is already offboarding")

    # Step-up: re-confirm the acting super admin's own identity (no MFA exists)
    if not verify_password(request.password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Identity re-confirmation failed",
        )

    # Set tenant context so session revocation and audit entry pass RLS
    await set_tenant_context(db, str(tenant_id))

    # Revoke all sessions for this tenant — lock takes effect immediately
    await db.execute(
        delete(Session).where(Session.tenant_id == tenant_id)
    )

    now = datetime.now(timezone.utc)
    tenant.status = TenantStatus.offboarding
    tenant.offboarded_at = now
    tenant.offboarded_by = current_user.id
    tenant.purge_after = now + timedelta(days=OFFBOARD_GRACE_DAYS)
    await db.flush()

    await write_audit_log(
        db=db,
        tenant_id=tenant.id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        action="offboard_tenant",
        target_type="tenant",
        target_id=tenant.id,
        details={"purge_after": tenant.purge_after.isoformat()},
    )

    await db.commit()
    await db.refresh(tenant)
    return tenant


@router.patch("/tenants/{tenant_id}/cancel-offboarding", response_model=TenantResponse)
async def cancel_offboarding(
    tenant_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """VQ-403: Cancel an offboarding within the grace period."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    if tenant.status != TenantStatus.offboarding:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tenant is not offboarding")

    # Set tenant context so the audit entry passes RLS
    await set_tenant_context(db, str(tenant_id))

    tenant.status = TenantStatus.active
    tenant.offboarded_at = None
    tenant.offboarded_by = None
    tenant.purge_after = None
    tenant.purged_at = None
    await db.flush()

    await write_audit_log(
        db=db,
        tenant_id=tenant.id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        action="cancel_offboarding",
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
    # Set the tenant context before the reads below, not just before the
    # inserts. This handler runs on a platform request, so it arrives with no
    # tenant in context and the tenant_isolation policy on users hides every
    # row. The "does this tenant already have a Client Admin" check would then
    # read zero rows, find none, and allow a second invite to be issued - a
    # silent check-then-act failure that only appears under the real app role.
    await set_tenant_context(db, str(tenant_id))
    print(f"DEBUG create_invite: tenant_id={tenant_id}, context set")

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    print(f"DEBUG create_invite: tenant query result={tenant}")

    if not tenant:
        print(f"DEBUG create_invite: TENANT NOT FOUND for id={tenant_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    if tenant.status != TenantStatus.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Can only invite for active tenants")

    # Set tenant context so queries pass RLS even under vaultiq_app
    await set_tenant_context(db, str(tenant_id))

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

    # Set tenant context so invite + audit inserts pass RLS even under vaultiq_app
    await set_tenant_context(db, str(tenant_id))

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
    # Re-set tenant context before refresh; the commit ended the transaction
    # and with it the SET LOCAL context. The invite has tenant_id so the
    # tenant_isolation policy requires the context to be present.
    await set_tenant_context(db, str(tenant_id))
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


@router.get("/tenants/{tenant_id}/settings", response_model=TenantSettingsResponse)
async def get_tenant_settings(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """VQ-304: Get all settings for a tenant (super_admin)."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    ts = await TenantSettingsService.get_settings(db, tenant_id)
    if not ts:
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


@router.patch("/tenants/{tenant_id}/settings", response_model=TenantSettingsResponse)
async def update_tenant_settings(
    tenant_id: UUID,
    request: TenantSettingsUpdateSuperAdmin,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """VQ-304: Update tenant settings (super_admin can change everything incl. storage_quota_mb)."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    await set_tenant_context(db, str(tenant_id))

    payload = request.model_dump(exclude_unset=True)
    ts = await TenantSettingsService.update_settings(
        db=db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        is_super_admin=True,
        payload=payload,
    )
    return ts


@router.post("/tenants/{tenant_id}/settings/logo", response_model=LogoUploadResponse)
async def upload_tenant_logo(
    tenant_id: UUID,
    file: bytes = File(...),
    filename: str = "logo.png",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """VQ-304: Upload tenant logo (super_admin)."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    await set_tenant_context(db, str(tenant_id))

    ts = await TenantSettingsService.update_settings(
        db=db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        is_super_admin=True,
        payload={},
        logo_file=file,
        logo_filename=filename,
    )
    return LogoUploadResponse(
        path=ts.logo_path,
        size_bytes=len(file),
        mime_type=magic.from_buffer(file, mime=True),
    )


@router.get("/deletion-reports", response_model=list[DeletionReportResponse])
async def list_deletion_reports(
    db: AsyncSession = Depends(get_db),
):
    """VQ-403: List deletion reports (platform-level, stored outside tenants)."""
    result = await db.execute(
        select(DeletionReport).order_by(DeletionReport.created_at.desc()).limit(200)
    )
    return result.scalars().all()


@router.get("/deletion-reports/{report_id}", response_model=DeletionReportResponse)
async def get_deletion_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """VQ-403: Fetch a single deletion report."""
    result = await db.execute(select(DeletionReport).where(DeletionReport.id == report_id))
    report = result.scalar_one_or_none()

    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deletion report not found")

    return report