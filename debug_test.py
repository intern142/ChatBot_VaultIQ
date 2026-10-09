import asyncio
import sys
sys.path.insert(0, '.')
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import get_settings
from app.auth.jwt import create_access_token
from uuid import UUID

async def test():
    settings = get_settings()
    # Create a super_admin token
    token = create_access_token(
        user_id=UUID('d40fa0ba-c2fa-4dcd-868d-c071186f1756'),
        role='super_admin',
        tenant_id=None,
        session_id=UUID('a1b2c3d4-e5f6-7890-abcd-ef1234567890')
    )
    print('Token:', token[:50] + '...')
    
    # Connect as vaultiq_app
    engine = create_async_engine(settings.DATABASE_URL_SYNC.replace('postgresql://', 'postgresql+asyncpg://'), echo=False)
    async with engine.begin() as conn:
        # Check if tenant exists
        result = await conn.execute(text("SELECT id, short_code FROM tenants WHERE short_code = 'TENANT_A'"))
        row = result.fetchone()
        print('Tenant from vaultiq_app:', row)
        
        if row:
            # Set tenant context
            await conn.execute(text("SELECT set_config('app.current_tenant', :tid, true)"), {'tid': str(row[0])})
            
            # Query again
            result = await conn.execute(text("SELECT id, short_code FROM tenants WHERE id = :tid"), {'tid': row[0]})
            row = result.fetchone()
            print('Tenant with context:', row)
    await engine.dispose()

asyncio.run(test())