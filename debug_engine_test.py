import asyncio
import sys
import os
sys.path.insert(0, '.')

os.environ['ADMIN_DATABASE_URL'] = "postgresql+asyncpg://vaultiq:vaultiq_secret@localhost:5433/vaultiq"
os.environ['APP_DATABASE_URL'] = "postgresql+asyncpg://vaultiq_app:vaultiq_secret@localhost:5433/vaultiq"
os.environ['DATABASE_URL_SYNC'] = "postgresql://vaultiq:vaultiq_secret@localhost:5433/vaultiq"

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from sqlalchemy.pool import NullPool

async def test():
    # Create engine 1
    engine1 = create_async_engine(
        "postgresql+asyncpg://vaultiq:vaultiq_secret@localhost:5433/vaultiq",
        echo=False,
        poolclass=NullPool,
    )
    
    # Truncate and insert via engine1
    async with engine1.begin() as conn:
        await conn.execute(text("TRUNCATE tenants CASCADE"))
        print("Truncated")
    
    async with engine1.begin() as conn:
        result = await conn.execute(text("INSERT INTO tenants (short_code, name, status, storage_quota_mb) VALUES ('TEST', 'Test', 'active', 100) RETURNING id"))
        tid = result.scalar()
        print(f"Inserted tenant id={tid}")
    
    # Verify via engine1 new connection
    async with engine1.begin() as conn:
        result = await conn.execute(text("SELECT id FROM tenants WHERE id = :tid"), {"tid": tid})
        row = result.fetchone()
        print(f"Verify via engine1: {row}")
    
    # Create engine2 (separate engine)
    engine2 = create_async_engine(
        "postgresql+asyncpg://vaultiq:vaultiq_secret@localhost:5433/vaultiq",
        echo=False,
        poolclass=NullPool,
    )
    
    # Verify via engine2
    async with engine2.begin() as conn:
        result = await conn.execute(text("SELECT id FROM tenants WHERE id = :tid"), {"tid": tid})
        row = result.fetchone()
        print(f"Verify via engine2: {row}")
    
    await engine1.dispose()
    await engine2.dispose()

asyncio.run(test())