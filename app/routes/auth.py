from datetime import datetime, timezone, timedelta
import asyncio
import hashlib
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import (
    apply_token_context,
    get_db,
    set_platform_context,
    set_reset_code_context,
    set_tenant_context,
)
from app.config import get_settings
from app.models.tenant import Tenant
from app.models.user import User
from app.models.session import Session
from app.models.reset_code import ResetCode
from app.models.audit_log import AuditLog
from app.auth.password import verify_password, hash_password, validate_password_strength
from app.auth.jwt import create_access_token, decode_token
from app.auth.dependencies import get_current_user
from app.auth.permissions import require_roles
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    RefreshRequest,
    MessageResponse,
    ResetPasswordRequest,
)
from app.schemas.tenant import TenantStatus

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
security = HTTPBearer()

LOGIN_DELAY = timedelta(milliseconds=200)


async def _check_lockout(user: User) -> bool:
    if user.locked_until and user.locked_until > datetime.now(timezone.utc):
        return True
    return False


async def _record_failed_login(user: User, db: AsyncSession):
    user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
    if user.failed_login_attempts >= settings.MAX_FAILED_ATTEMPTS:
        user.locked_until = datetime.now(timezone.utc) + timedelta(
            minutes=settings.LOCKOUT_DURATION_MINUTES
        )
    await db.commit()


async def _reset_failed_logins(user: User, db: AsyncSession):
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.commit()


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    start = datetime.now(timezone.utc)

    if request.organisation_code == "SUPER":
        # Platform rows carry tenant_id IS NULL and are invisible to the tenant
        # policy, so the platform context has to be set before the lookup, not
        # after it. organisation_code is caller input, but it only decides which
        # of two lookups runs; the policy still requires role = 'super_admin' and
        # app.platform_access, so guessing "SUPER" grants nothing on its own.
        await set_platform_context(db)
        result = await db.execute(
            select(User).where(
                User.email == request.email,
                User.tenant_id.is_(None),
                User.role == "super_admin",
            )
        )
        user = result.scalar_one_or_none()
    else:
        result = await db.execute(
            select(Tenant).where(Tenant.short_code == request.organisation_code)
        )
        tenant = result.scalar_one_or_none()

        user = None
        if tenant:
            await set_tenant_context(db, str(tenant.id))
            result = await db.execute(
                select(User).where(
                    User.email == request.email,
                    User.tenant_id == tenant.id,
                )
            )
            user = result.scalar_one_or_none()

    if user:
        if user.tenant_id:
            result = await db.execute(select(Tenant).where(Tenant.id == user.tenant_id))
            tenant = result.scalar_one_or_none()
            if tenant and tenant.status in (TenantStatus.suspended, TenantStatus.offboarding):
                elapsed = (datetime.now(timezone.utc) - start).total_seconds()
                if elapsed < LOGIN_DELAY.total_seconds():
                    await asyncio.sleep(LOGIN_DELAY.total_seconds() - elapsed)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Tenant suspended",
                )

        locked = await _check_lockout(user)
        if locked:
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            if elapsed < LOGIN_DELAY.total_seconds():
                await asyncio.sleep(LOGIN_DELAY.total_seconds() - elapsed)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        # VQ-301 AC3: a deactivated account cannot get a new session.
        #
        # This is the same 401 with the same body and the same floor as the lockout
        # above, and it sits before the password check on purpose. Not after: a
        # deactivated user who still types the right password must not be told
        # anything the wrong-password path would not tell them, and an attacker
        # must not be able to distinguish "deactivated" from "wrong password" by
        # the response or by how long it took. Reaching the bcrypt work first and
        # rejecting after it would leak both.
        if not user.is_active:
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            if elapsed < LOGIN_DELAY.total_seconds():
                await asyncio.sleep(LOGIN_DELAY.total_seconds() - elapsed)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        if not verify_password(request.password, user.password_hash):
            await _record_failed_login(user, db)
            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            if elapsed < LOGIN_DELAY.total_seconds():
                await asyncio.sleep(LOGIN_DELAY.total_seconds() - elapsed)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )

        await _reset_failed_logins(user, db)

    else:
        elapsed = (datetime.now(timezone.utc) - start).total_seconds()
        if elapsed < LOGIN_DELAY.total_seconds():
            await asyncio.sleep(LOGIN_DELAY.total_seconds() - elapsed)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if user.tenant_id:
        await set_tenant_context(db, str(user.tenant_id))
    else:
        # Re-set rather than rely on the one set before the lookup above. Any
        # commit in between - including the failed-login bookkeeping - ends the
        # transaction, and set_config(..., true) is transaction-scoped, so the
        # context is gone by this point. Without it the session INSERT below
        # has no matching policy and fails with InsufficientPrivilegeError.
        await set_platform_context(db)

    session = Session(
        user_id=user.id,
        tenant_id=user.tenant_id,
        token_hash="",
        expires_at=datetime.now(timezone.utc)
        + timedelta(hours=settings.JWT_EXPIRATION_HOURS),
    )
    db.add(session)
    await db.commit()

    token = create_access_token(
        user_id=user.id,
        role=user.role,
        tenant_id=user.tenant_id,
        session_id=session.id,
    )

    return TokenResponse(
        access_token=token,
        role=user.role,
        tenant_id=user.tenant_id,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Session).where(
            Session.user_id == user.id,
            Session.is_revoked == False,
        )
    )
    active_session = result.scalar_one_or_none()

    if active_session:
        active_session.is_revoked = True
        active_session.revoked_at = datetime.now(timezone.utc)
        await db.commit()

    if user.tenant_id:
        await set_tenant_context(db, str(user.tenant_id))
    else:
        # After the commit above the transaction, and with it the platform
        # context, is gone. The SELECT at the top of this handler ran inside
        # whatever context get_current_user left behind, so it is re-established
        # here before the new session row is written.
        await set_platform_context(db)

    new_session = Session(
        user_id=user.id,
        tenant_id=user.tenant_id,
        token_hash="",
        expires_at=datetime.now(timezone.utc)
        + timedelta(hours=settings.JWT_EXPIRATION_HOURS),
    )
    db.add(new_session)
    await db.commit()

    token = create_access_token(
        user_id=user.id,
        role=user.role,
        tenant_id=user.tenant_id,
        session_id=new_session.id,
    )

    return TokenResponse(
        access_token=token,
        role=user.role,
        tenant_id=user.tenant_id,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    jti = payload.get("jti")
    await apply_token_context(db, payload)
    result = await db.execute(select(Session).where(Session.id == jti))
    session = result.scalar_one_or_none()

    if session:
        session.is_revoked = True
        session.revoked_at = datetime.now(timezone.utc)
        await db.commit()

return MessageResponse(detail="Logged out")


# ---------------------------------------------------------------------------
# VQ-301: password reset, consumed with a one-time code
# ---------------------------------------------------------------------------

# Every way this endpoint can fail produces this same status, this same body and
# at least this much elapsed time. The caller holds no session, so a difference
# in response is the only signal they get about whether a code exists, whether
# it was already used, or whether it has expired. There must not be one.
RESET_FAILURE_DETAIL = "Invalid or expired reset code"
RESET_MIN_ELAPSED = timedelta(milliseconds=200)


async def _reject_reset(started: datetime) -> None:
    elapsed = datetime.now(timezone.utc) - started
    if elapsed < RESET_MIN_ELAPSED:
        await asyncio.sleep((RESET_MIN_ELAPSED - elapsed).total_seconds())
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=RESET_FAILURE_DETAIL,
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Set a new password using a one-time code issued by a Client Admin.

    Unauthenticated by design: this is the path a locked-out user takes. The
    code is the only credential presented.
    """
    started = datetime.now(timezone.utc)

    # Checked before the code is looked at, so a weak password cannot be used to
    # probe whether a code is real, and so a rejected password leaves the code
    # unconsumed and still usable.
    errors = validate_password_strength(request.new_password)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password does not meet the minimum requirements",
        )

    code_hash = hashlib.sha256(request.code.encode("utf-8")).hexdigest()

    # Grants exactly one capability to a no-context session: reading the row
    # whose stored hash matches the hash the caller already holds.
    await set_reset_code_context(db, code_hash)
    result = await db.execute(
        select(ResetCode).where(ResetCode.code_hash == code_hash)
    )
    reset_code = result.scalar_one_or_none()
    if reset_code is None:
        await _reject_reset(started)

    now = datetime.now(timezone.utc)
    if reset_code.used_at is not None or reset_code.expires_at <= now:
        await _reject_reset(started)

    # The context now comes from the row the code unlocked, never from the
    # request. Without this, the user update below would run as a no-tenant
    # session and RLS would silently match nothing.
    await set_tenant_context(db, str(reset_code.tenant_id))

    # Claim the code with one conditional statement. Reading `used_at` and then
    # writing it would let two requests holding the same valid code both succeed;
    # the WHERE clause makes the second one match zero rows.
    claimed = await db.execute(
        update(ResetCode)
        .where(
            ResetCode.id == reset_code.id,
            ResetCode.used_at.is_(None),
            ResetCode.expires_at > now,
        )
        .values(used_at=now)
        .returning(ResetCode.id)
    )
    if claimed.scalar_one_or_none() is None:
        await db.rollback()
        await _reject_reset(started)

    result = await db.execute(select(User).where(User.id == reset_code.user_id))
    user = result.scalar_one_or_none()
    if user is None:
        await db.rollback()
        await _reject_reset(started)

    user.password_hash = hash_password(request.new_password)
    # A reset is also the way out of a lockout, so the counter and the lock are
    # cleared here. Leaving them would hand the user a valid new password that
    # still cannot be used.
    user.failed_login_attempts = 0
    user.locked_until = None

    # Sign the account out everywhere. A password reset is the usual response to
    # a suspected compromise; leaving old sessions alive would defeat that.
    await db.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.is_revoked == False)
        .values(is_revoked=True, revoked_at=now)
    )

    db.add(
        AuditLog(
            tenant_id=user.tenant_id,
            actor_user_id=user.id,
            actor_role=user.role,
            action="complete_password_reset",
            target_type="user",
            target_id=user.id,
            details={"sessions_revoked": True},
        )
    )

    await db.commit()

    return MessageResponse(
        detail="Password updated. All existing sessions have been signed out."
    )
