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
    """Set tenant context for RLS using set_config (transaction-scoped, auto-resets).

    set_config takes a bound parameter, unlike SET. The previous version built
    the statement with f-string interpolation because asyncpg cannot bind
    parameters inside SET, which put a caller-influenced value into SQL text.
    """
    await session.execute(
        text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
        {"tenant_id": tenant_id},
    )


async def clear_tenant_context(session: AsyncSession) -> None:
    """Clear tenant context (not strictly needed with set_config, but explicit)."""
    await session.execute(
        text("SELECT set_config('app.current_tenant', '', true)"),
    )


async def apply_token_context(session: AsyncSession, payload: dict) -> None:
    """Apply tenant context from JWT payload for RLS.

    The payload contains tenant_id (or None for super_admin). This sets the
    context before any database queries so RLS policies see the correct tenant.
    """
    tenant_id = payload.get("tenant_id")
    if tenant_id:
        await set_tenant_context(session, str(tenant_id))
    else:
        # Super admin: no tenant context
        await clear_tenant_context(session)


async def set_platform_context(session: AsyncSession) -> None:
    """Set platform access context for super_admin (no tenant)."""
    await session.execute(
        text("SELECT set_config('app.platform_access', 'on', true)")
    )
    await clear_tenant_context(session)


async def set_reset_code_context(session: AsyncSession, code_hash: str) -> None:
    """Set reset code context for password reset lookup."""
    await session.execute(
        text("SELECT set_config('app.reset_code_hash', :code_hash, true)"),
        {"code_hash": code_hash},
    )