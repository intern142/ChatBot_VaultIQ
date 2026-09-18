import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text
from app.auth.password import hash_password
from app.config import get_settings

async def main():
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    tenant_id = "6ffb4d73-4bf3-42cd-aeb4-30a77cf76019"
    
    async with async_session() as session:
        await session.execute(text("DELETE FROM users WHERE email IN ('superadmin@vaultiq.io', 'clientadmin@acme.com', 'employee@acme.com')"))
        
        await session.execute(text("""
            INSERT INTO users (tenant_id, email, password_hash, role) 
            VALUES (NULL, 'superadmin@vaultiq.io', :hash, 'super_admin')
        """), {'hash': hash_password('SuperAdmin1!')})
        
        await session.execute(text("""
            INSERT INTO users (tenant_id, email, password_hash, role) 
            VALUES (:tid, 'clientadmin@acme.com', :hash, 'client_admin')
        """), {'tid': tenant_id, 'hash': hash_password('ClientAdmin1!')})
        
        await session.execute(text("""
            INSERT INTO users (tenant_id, email, password_hash, role) 
            VALUES (:tid, 'employee@acme.com', :hash, 'employee')
        """), {'tid': tenant_id, 'hash': hash_password('Employee1!')})
        
        await session.commit()
    await engine.dispose()
    print('Users created successfully')

asyncio.run(main())