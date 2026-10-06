from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "development",
    poolclass=NullPool,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def set_tenant_context(session: AsyncSession, tenant_id: str) -> None:
    await session.execute(
        text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
        {"tenant_id": tenant_id},
    )


async def clear_tenant_context(session: AsyncSession) -> None:
    """Clear tenant context (not strictly needed with SET LOCAL, but explicit)."""
    await session.execute(text("SET LOCAL app.current_tenant = ''"))


async def set_platform_context(session: AsyncSession) -> None:
    """Set platform context so Super Admin rows are reachable under RLS.

    Known Defect #2. Platform accounts have tenant_id IS NULL (VQ-101 AC3), and
    the platform_account_access policies in migration 009 require
    app.platform_access = 'on' before such a row is visible. Only call this on a
    path that has already established the caller is a Super Admin - it is the
    one context that deliberately reaches outside any tenant.

    The tenant context is cleared first on purpose. The policy also requires
    that no tenant be in context, so that setting both can never widen
    visibility rather than just failing. Clearing first means the policy's
    conditions are satisfied by construction on a platform path.
    """
    await session.execute(text("SELECT set_config('app.current_tenant', '', true)"))
    await session.execute(text("SELECT set_config('app.platform_access', 'on', true)"))


async def apply_token_context(session: AsyncSession, payload: dict) -> None:
    """Set the RLS context implied by a token payload.

    Every route that resolves a token calls this, rather than each one deciding
    for itself. The reason is a security property, not tidiness: the decision
    has to be identical everywhere, because a path that quietly forgets to set
    the platform context produces a Super Admin 401, and a path that guesses it
    wrong produces a leak. One function is one thing to review.

    The payload is a decoded but not-yet-authorised token, so the role claim
    here is a hint and not a permission. It is safe to act on because the RLS
    policy it selects still requires the row itself to be tenant_id IS NULL AND
    role = 'super_admin'. Presenting a tenant token with a forged super_admin
    claim therefore does not reach platform rows: the session and user lookups
    that follow are keyed on this token's own sub and jti, which are tenant
    rows, and a tenant row does not match the platform policy. The outcome is a
    401, never additional visibility.

    A tenant token can never select the platform context by omitting its tenant,
    because the role claim is required as well as the missing tenant.
    """
    tenant_id = payload.get("tenant_id")
    if tenant_id:
        await set_tenant_context(session, str(tenant_id))
    elif payload.get("role") == "super_admin":
        await set_platform_context(session)
