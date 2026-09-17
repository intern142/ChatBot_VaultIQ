import pytest
import pytest_asyncio
import psycopg2
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import get_settings
from app import database

settings = get_settings()


@pytest.fixture(scope="function")
def db_conn():
    conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute("TRUNCATE users, tenants, sessions CASCADE")
    conn.commit()
    yield conn
    conn.close()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def override_db_engine():
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=False,
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    from app.database import get_db
    database.engine = engine
    database.AsyncSessionLocal = session_factory

    yield

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(override_db_engine, db_conn):
    from sqlalchemy import text
    session_factory = async_sessionmaker(
        database.engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        await session.execute(text("TRUNCATE users, tenants, sessions CASCADE"))
        await session.commit()
        yield session
