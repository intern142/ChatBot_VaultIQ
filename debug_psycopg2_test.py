import asyncio
import sys
sys.path.insert(0, '.')

from tests.conftest import ADMIN_DATABASE_URL
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from sqlalchemy.pool import NullPool
import psycopg2

async def test():
    # Create engine
    engine = create_async_engine(
        ADMIN_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )
    
    # Truncate and insert via engine
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE tenants CASCADE"))
        print("Truncated")
    
    async with engine.begin() as conn:
        result = await conn.execute(text("INSERT INTO tenants (short_code, name, status, storage_quota_mb) VALUES ('TEST', 'Test', 'active', 100) RETURNING id"))
        tid = result.scalar()
        print(f"Inserted tenant id={tid}")
    
    # Verify via engine new connection
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT id FROM tenants WHERE id = :tid"), {"tid": tid})
        row = result.fetchone()
        print(f"Verify via engine: {row}")
    
    # Now check via psycopg2 (separate connection)
    sync_url = ADMIN_DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://')
    pg_conn = psycopg2.connect(sync_url)
    pg_conn.autocommit = True
    with pg_conn.cursor() as cur:
        cur.execute("SELECT id FROM tenants WHERE id = %s", (str(tid),))
        row = cur.fetchone()
        print(f"Verify via psycopg2: {row}")
    pg_conn.close()
    
    await engine.dispose()

asyncio.run(test())