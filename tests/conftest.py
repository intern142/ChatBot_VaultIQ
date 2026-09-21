import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from app.config import get_settings

settings = get_settings()


@pytest.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(db_engine):
    async with db_engine.begin() as conn:
        await conn.execute(text("TRUNCATE users, tenants CASCADE"))
    session_factory = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session


@pytest.fixture(scope="function")
async def app_db_engine():
    """Engine connected as vaultiq_app role (no BYPASSRLS)."""
    app_url = settings.DATABASE_URL.replace("vaultiq:vaultiq_secret", "vaultiq_app:vaultiq_secret")
    engine = create_async_engine(
        app_url,
        echo=False,
        pool_pre_ping=True,
    )
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def app_db_session(app_db_engine):
    """Async session as vaultiq_app role - RLS enforced."""
    # Use admin engine for cleanup (vaultiq_app has no TRUNCATE privilege)
    admin_engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )
    async with admin_engine.begin() as conn:
        await conn.execute(text("TRUNCATE users, tenants, sessions CASCADE"))
    await admin_engine.dispose()
    session_factory = async_sessionmaker(
        app_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
