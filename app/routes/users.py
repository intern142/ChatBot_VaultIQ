"""VQ-301: Client Admin user management.

Separate from `app/routes/admin.py`, and deliberately mounted at `/users`
rather than `/admin`.

Two reasons, both about keeping a rule intact rather than adding exceptions:

  * `app/routes/admin.py` carries `require_roles("super_admin")` at router
    level, so a Client Admin endpoint cannot live there.
  * `test_tenant_lifecycle.py` asserts that *every* `/admin/*` operation in
    ROLE_MATRIX is Super Admin only, and there are exactly six of them. Putting
    a tenant-scoped operation under `/admin` would have meant weakening that
    test or deleting the invariant. `/admin` keeps meaning "platform operator";
    this operation is the client managing its own people, which is a different
    thing and deserves a different path.

VQ-106 AC4 denies Super Admin document-content operations, and the Sprint 3
specs name the Client Admin as the actor for tenant-scoped work.
"""
import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.permissions import require_roles
from app.config import get_settings
from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.reset_code import ResetCode
from app.models.user import User
from app.schemas.user import PasswordResetIssued

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_roles("client_admin"))],
)
settings = get_settings()


def generate_reset_code() -> str:
    """32 bytes -> 43 char base64url, same shape as the invite codes."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii").rstrip("=")


def hash_reset_code(code: str) -> str:
    """SHA-256 hex digest.

    The plaintext code is a bearer credential that can set the account's
    password, so it is never stored. Nothing here is a substitute for the
    entropy of the code itself; it only means a database read does not hand
    over a working reset.
    """
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


async def write_audit_log(
    db: AsyncSession,
    tenant_id: UUID,
    actor_user_id: Optional[UUID],
    actor_role: str,
    action: str,
    target_type: str,
    target_id: UUID,
    details: dict[str, Any],
) -> None:
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


@router.post(
    "/{user_id}/password-reset",
    response_model=PasswordResetIssued,
    status_code=status.HTTP_201_CREATED,
)
async def issue_password_reset(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Issue a one-time reset code for a user in the caller's own tenant.

    The code is returned in the body for the Client Admin to hand over. It is
    the only moment the plaintext exists server-side, and no internal mail relay
    is contacted, per the no-internet rule.
    """
    # Self-target is refused rather than served. The admin already has a valid
    # session, and issuing themselves a code they then have to consume
    # unauthenticated is a way to lock yourself out of your own account.
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use the change-password flow to change your own password",
        )

    # No explicit tenant filter: get_current_user has already set the tenant
    # context from the verified token, so RLS restricts this read to the
    # caller's own tenant. A user id belonging to another tenant is therefore
    # simply not found, which is the 404-not-403 rule from VQ-103.
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=settings.RESET_CODE_EXPIRY_HOURS)

    # Cap the number of live codes per user and drop the oldest, so a lost code
    # cannot permanently block a reset and old codes do not accumulate.
    live = await db.execute(
        select(ResetCode)
        .where(
            ResetCode.user_id == user_id,
            ResetCode.used_at.is_(None),
            ResetCode.expires_at > now,
        )
        .order_by(ResetCode.created_at.asc())
    )
    live_codes = list(live.scalars().all())
    overflow = len(live_codes) - (settings.RESET_CODE_MAX_LIVE_PER_USER - 1)
    for stale in live_codes[:overflow] if overflow > 0 else []:
        await db.delete(stale)

    code = generate_reset_code()
    db.add(
        ResetCode(
            tenant_id=target.tenant_id,
            user_id=target.id,
            code_hash=hash_reset_code(code),
            expires_at=expires_at,
            created_by=current_user.id,
        )
    )

    await write_audit_log(
        db=db,
        tenant_id=target.tenant_id,
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        action="request_password_reset",
        target_type="user",
        target_id=target.id,
        details={"expires_at": expires_at.isoformat()},
    )

    await db.commit()

    return PasswordResetIssued(reset_code=code, expires_at=expires_at)
