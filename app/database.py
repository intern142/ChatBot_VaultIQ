from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_ENV == "development",
    pool_pre_ping=True,
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
    """Set tenant context for RLS using SET LOCAL (transaction-scoped, auto-resets)."""
    # Use literal string interpolation for SET LOCAL (asyncpg doesn't support params for SET)
    await session.execute(text(f"SET LOCAL app.current_tenant = '{tenant_id}'"))


async def clear_tenant_context(session: AsyncSession) -> None:
    """Clear tenant context (not strictly needed with SET LOCAL, but explicit)."""
    await session.execute(text("SET LOCAL app.current_tenant = ''"))
