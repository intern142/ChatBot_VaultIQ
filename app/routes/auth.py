from datetime import datetime, timezone, timedelta
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.config import get_settings
from app.models.tenant import Tenant
from app.models.user import User
from app.models.session import Session
from app.auth.password import verify_password, hash_password, validate_password_strength
from app.auth.jwt import create_access_token, decode_token
from app.auth.dependencies import get_current_user
from app.auth.permissions import require_roles
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest, MessageResponse
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

    session = Session(
        user_id=user.id,
        tenant_id=user.tenant_id,
        token_hash="",
        expires_at=datetime.now(timezone.utc)
        + timedelta(hours=settings.JWT_EXPIRATION_HOURS),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

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
    if user.role not in ("super_admin", "client_admin", "employee"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
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

    new_session = Session(
        user_id=user.id,
        tenant_id=user.tenant_id,
        token_hash="",
        expires_at=datetime.now(timezone.utc)
        + timedelta(hours=settings.JWT_EXPIRATION_HOURS),
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)

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

    role = payload.get("role")
    if role not in ("super_admin", "client_admin", "employee"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    jti = payload.get("jti")
    result = await db.execute(select(Session).where(Session.id == jti))
    session = result.scalar_one_or_none()

    if session:
        session.is_revoked = True
        session.revoked_at = datetime.now(timezone.utc)
        await db.commit()

    return MessageResponse(detail="Logged out")
