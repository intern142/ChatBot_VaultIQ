"""Feature 2: Client-admin delegated actions (add users, create tenants).

Endpoints require client_admin role AND the corresponding tenant permission
(can_add_users / can_create_tenants) to be granted by a Super Admin.
"""
import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.database import get_db, set_tenant_context
from app.auth.dependencies import get_current_user_with_tenant
from app.auth.permissions import require_roles_with_tenant
from app.auth.password import hash_password, validate_password_strength
from app.models.tenant import Tenant
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.tenant import (
    TenantCreate,
    TenantResponse,
    ClientUserCreate,
    ClientFirstAdminCreate,
    UserRole,
    TenantStatus,
)
from app.schemas.user import UserResponse

router = APIRouter(prefix="/client", tags=["client"], dependencies=[Depends(require_roles_with_tenant("client_admin"))])


async def write_audit_log(
    db: AsyncSession,
    tenant_id: UUID,
    actor_user_id: UUID | None,
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


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: ClientUserCreate,
    current_user_tenant: tuple[User, str] = Depends(require_roles_with_tenant("client_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a user in the caller's own tenant (requires can_add_users)."""
    current_user, tenant_id_str = current_user_tenant
    tenant_uuid = UUID(tenant_id_str)

    result = await db.execute(select(Tenant).where(Tenant.id == tenant_uuid))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    if not tenant.can_add_users:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant not permitted to add users",
        )

    # Validate password strength
    errors = validate_password_strength(request.password)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(errors),
        )

    # Enforce single Client Admin per tenant
    if request.role == UserRole.client_admin:
        result = await db.execute(
            select(User).where(User.tenant_id == tenant_uuid, User.role == "client_admin")
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant already has a Client Admin",
            )

    # Check email uniqueness in this tenant
    result = await db.execute(
        select(User).where(User.tenant_id == tenant_uuid, User.email == request.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    user = User(
        tenant_id=tenant_uuid,
        email=request.email,
        password_hash=hash_password(request.password),
        role=request.role.value,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    await write_audit_log(
        db=db,
        tenant_id=tenant_uuid,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        action="create_user",
        target_type="user",
        target_id=user.id,
        details={"email": user.email, "role": user.role},
    )

    await db.commit()
    await db.refresh(user)
    return user


@router.post("/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    request: TenantCreate,
    current_user_tenant: tuple[User, str] = Depends(require_roles_with_tenant("client_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create a new tenant (requires can_create_tenants)."""
    current_user, tenant_id_str = current_user_tenant
    own_tenant_uuid = UUID(tenant_id_str)

    result = await db.execute(select(Tenant).where(Tenant.id == own_tenant_uuid))
    own_tenant = result.scalar_one_or_none()
    if not own_tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    if not own_tenant.can_create_tenants:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant not permitted to create tenants",
        )

    new_tenant = Tenant(
        short_code=request.short_code.upper(),
        name=request.name,
        storage_quota_mb=request.storage_quota_mb,
        status=TenantStatus.active,
        created_by_user_id=current_user.id,
    )
    db.add(new_tenant)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tenant short code already exists",
        )

    # Switch context to the new tenant so audit writes pass FORCE RLS
    await set_tenant_context(db, str(new_tenant.id))

    await write_audit_log(
        db=db,
        tenant_id=new_tenant.id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        action="create_tenant",
        target_type="tenant",
        target_id=new_tenant.id,
        details={
            "short_code": new_tenant.short_code,
            "name": new_tenant.name,
            "storage_quota_mb": new_tenant.storage_quota_mb,
        },
    )

    await db.commit()
    await db.refresh(new_tenant)
    return new_tenant


@router.post("/tenants/{tenant_id}/first-admin", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_first_admin(
    tenant_id: UUID,
    request: ClientFirstAdminCreate,
    current_user_tenant: tuple[User, str] = Depends(require_roles_with_tenant("client_admin")),
    db: AsyncSession = Depends(get_db),
):
    """Create the first Client Admin for a tenant created by this client admin."""
    current_user, own_tenant_id_str = current_user_tenant
    own_tenant_uuid = UUID(own_tenant_id_str)

    # Verify the target tenant exists and was created by this user
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    target_tenant = result.scalar_one_or_none()

    if not target_tenant or target_tenant.created_by_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )

    # Permission gate: the client admin's own tenant must have the create-tenants grant
    result = await db.execute(select(Tenant).where(Tenant.id == own_tenant_uuid))
    own_tenant = result.scalar_one_or_none()
    if not own_tenant or not own_tenant.can_create_tenants:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant not permitted to create tenants",
        )

    # Target tenant must be active
    if target_tenant.status != TenantStatus.active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only set up admin for active tenants",
        )

    # Ensure no Client Admin exists yet
    result = await db.execute(
        select(User).where(User.tenant_id == tenant_id, User.role == "client_admin")
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant already has a Client Admin",
        )

    # Check email uniqueness in target tenant
    result = await db.execute(
        select(User).where(User.tenant_id == tenant_id, User.email == request.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    # Validate password
    errors = validate_password_strength(request.password)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="; ".join(errors),
        )

    # Switch to target tenant context for the insert (FORCE RLS on users)
    await set_tenant_context(db, str(tenant_id))

    user = User(
        tenant_id=tenant_id,
        email=request.email,
        password_hash=hash_password(request.password),
        role="client_admin",
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    await write_audit_log(
        db=db,
        tenant_id=tenant_id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        action="create_first_admin",
        target_type="user",
        target_id=user.id,
        details={"email": user.email},
    )

    await db.commit()
    await db.refresh(user)
    return user