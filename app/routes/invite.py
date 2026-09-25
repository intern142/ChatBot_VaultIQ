"""VQ-107: Public invite acceptance endpoint.

Accepting an invite is a bootstrap operation: the caller is not yet a tenant
user and supplies only the invite code. The code is a high-entropy secret
(256-bit), so the lookup is allowed through a dedicated RLS policy keyed on the
exact code (app.invite_accept_code) rather than tenant context. All writes that
follow run under the invite's tenant context so FORCE RLS on users / invites /
audit_logs is satisfied even when the connection uses the vaultiq_app role.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, set_tenant_context
from app.auth.password import hash_password, validate_password_strength
from app.models.tenant import Tenant
from app.models.user import User
from app.models.invite import Invite
from app.models.audit_log import AuditLog
from app.schemas.tenant import InviteAcceptRequest, InviteAcceptResponse, TenantStatus

router = APIRouter(tags=["invite"])

INVITE_CODE_PATTERN = "^[A-Za-z0-9_-]{20,64}$"


@router.post("/invite/accept", response_model=InviteAcceptResponse)
async def accept_invite(
    request: InviteAcceptRequest,
    db: AsyncSession = Depends(get_db),
):
    """Accept an invite and create the first Client Admin user for a tenant."""
    code = request.code.strip()
    if not code or len(code) > 64:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired invite")

    errors = validate_password_strength(request.password)
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="; ".join(errors))

    # Enable the code-lookup RLS policy (transaction-scoped, bound param — no injection)
    await db.execute(
        text("SELECT set_config('app.invite_accept_code', :code, true)"),
        {"code": code},
    )

    result = await db.execute(
        select(Invite).where(
            Invite.code == code,
            Invite.used_at.is_(None),
            Invite.expires_at > datetime.now(timezone.utc),
        )
    )
    invite = result.scalar_one_or_none()

    if not invite:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired invite")

    result = await db.execute(select(Tenant).where(Tenant.id == invite.tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant or tenant.status != TenantStatus.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired invite")

    # Check if tenant already has a client_admin
    result = await db.execute(
        select(User).where(User.tenant_id == invite.tenant_id, User.role == "client_admin")
    )
    existing_admin = result.scalar_one_or_none()
    if existing_admin:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant already has a Client Admin")

    # Check if user with this email already exists for this tenant
    result = await db.execute(
        select(User).where(User.tenant_id == invite.tenant_id, User.email == invite.email)
    )
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User with this email already exists")

    # All subsequent writes happen under the invite's tenant context (FORCE RLS)
    await set_tenant_context(db, str(invite.tenant_id))

    user = User(
        tenant_id=invite.tenant_id,
        email=invite.email,
        password_hash=hash_password(request.password),
        role="client_admin",
    )
    db.add(user)
    await db.flush()

    invite.used_at = datetime.now(timezone.utc)
    await db.flush()

    audit = AuditLog(
        tenant_id=invite.tenant_id,
        actor_user_id=None,
        actor_role="system",
        action="accept_invite",
        target_type="user",
        target_id=user.id,
        details={"email": user.email, "invite_id": str(invite.id)},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(user)

    return InviteAcceptResponse(
        detail="Invite accepted successfully. You can now log in.",
        tenant_id=invite.tenant_id,
        user_id=user.id,
    )