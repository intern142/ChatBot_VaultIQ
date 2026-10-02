"""Invite acceptance.

Accepting an invite is a bootstrap operation: the caller is not yet a tenant
user and supplies only the invite code. The code is a high-entropy secret
(256-bit), so the lookup is allowed through a dedicated RLS policy keyed on the
exact code (app.invite_accept_code) rather than tenant context. All writes that
follow run under the invite's tenant context so FORCE RLS on users / invites /
audit_logs is satisfied even when the connection uses the vaultiq_app role.

Written for VQ-107 (the first Client Admin of a tenant), extended by VQ-301 AC1
(a Client Admin inviting staff). The only behavioural change is that the created
user's role comes from `invite.role` rather than being hardcoded, and the
one-Client-Admin refusal is scoped to invites that actually ask for that role.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
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

    # VQ-107 AC3 is about bootstrapping: a tenant gets exactly one first Client
    # Admin. VQ-301 AC1 adds the other case, an invite for an employee or for a
    # second admin, and those must not be blocked by the bootstrap rule. So the
    # check is scoped to the role the invite actually asks for. An invite for a
    # client_admin still refuses when one exists, which is the VQ-107 behaviour,
    # unchanged.
    if invite.role == "client_admin":
        result = await db.execute(
            select(User).where(
                User.tenant_id == invite.tenant_id, User.role == "client_admin"
            )
        )
        existing_admin = result.scalar_one_or_none()
        if existing_admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant already has a Client Admin",
            )

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
        # VQ-301 AC1: the role the invite carries, not a hardcoded one.
        role=invite.role,
        is_active=True,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        # The unique (tenant_id, email) constraint is the real authority, and the
        # existence check above is a check-then-act that another writer can beat.
        # The reachable case is a CSV import that created this address while the
        # invite was outstanding: /users/import only reads the users table, so it
        # cannot see the pending invite. Without this the caller gets a 500 and
        # the password they just chose is silently discarded.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "A user with this email already exists. If that is you, use the "
                "password-reset flow instead of the invite."
            ),
        )

    invite.used_at = datetime.now(timezone.utc)
    await db.flush()

    audit = AuditLog(
        tenant_id=invite.tenant_id,
        actor_user_id=None,
        actor_role="system",
        action="accept_invite",
        target_type="user",
        target_id=user.id,
        # role recorded because it is no longer implied by the action name. The
        # invite code is deliberately not here: it is a live credential for the
        # moment the user sets their password, and audit_logs is a long-lived table.
        details={
            "email": user.email,
            "invite_id": str(invite.id),
            "role": user.role,
        },
    )
    db.add(audit)

    await db.commit()
    # Re-set tenant context before refresh; commit ended the transaction
    # and with it the SET LOCAL context. The user has tenant_id so the
    # tenant_isolation policy requires the context to be present.
    await set_tenant_context(db, str(invite.tenant_id))
    await db.refresh(user)

    return InviteAcceptResponse(
        detail="Invite accepted successfully. You can now log in.",
        tenant_id=invite.tenant_id,
        user_id=user.id,
    )