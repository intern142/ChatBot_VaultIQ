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
    """Set tenant context for RLS, transaction-scoped so it auto-resets on commit.

    asyncpg cannot bind parameters in SET, so the literal-interpolation form
    f"SET LOCAL app.current_tenant = '{id}'" was the previous approach. That put a
    caller-influenced value into SQL text. set_config takes the value as a bound
    parameter, so the tenant id never becomes part of the statement.
    """
    await session.execute(
        text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
        {"tenant_id": tenant_id},
    )


async def clear_tenant_context(session: AsyncSession) -> None:
    """Clear tenant context (not strictly needed with SET LOCAL, but explicit)."""
    await session.execute(text("SET LOCAL app.current_tenant = ''"))