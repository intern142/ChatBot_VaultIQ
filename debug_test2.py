import asyncio
import sys
sys.path.insert(0, '.')
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import get_settings
from app.auth.jwt import create_access_token
from uuid import UUID
from app.database import set_tenant_context, set_platform_context

async def test():
    settings = get_settings()
    # Create a super_admin token
    token = create_access_token(
        user_id=UUID('47978e2a-282a-4acc-a6cd-71f183204f19'),
        role='super_admin',
        tenant_id=None,
        session_id=UUID('b6b2c7a8-e9f0-4c3d-a2b1-c0d9e8f7a6b5')
    )
    print('Token:', token[:50] + '...')
    
    # Connect as vaultiq_app
    engine = create_async_engine(settings.DATABASE_URL_SYNC.replace('postgresql://', 'postgresql+asyncpg://'), echo=True)
    async with engine.begin() as conn:
        # First, check if tenant exists without any context
        result = await conn.execute(text("SELECT id, short_code FROM tenants WHERE short_code = 'TENANT_A'"))
        row = result.fetchone()
        print('Tenant without context:', row)
        
        if row:
            tenant_id = row[0]
            # Simulate what get_current_user does for super_admin
            await set_platform_context(conn)
            print('After set_platform_context')
            result = await conn.execute(text("SHOW app.current_tenant"))
            print('current_tenant:', result.scalar())
            result = await conn.execute(text("SHOW app.platform_access"))
            print('platform_access:', result.scalar())
            
            # Now simulate what create_invite does
            await set_tenant_context(conn, str(tenant_id))
            print('After set_tenant_context')
            result = await conn.execute(text("SHOW app.current_tenant"))
            print('current_tenant:', result.scalar())
            result = await conn.execute(text("SHOW app.platform_access"))
            print('platform_access:', result.scalar())
            
            # Now query the tenant
            result = await conn.execute(text("SELECT id, short_code FROM tenants WHERE id = :tid"), {'tid': tenant_id})
            row = result.fetchone()
            print('Tenant with context:', row)
    await engine.dispose()

asyncio.run(test())