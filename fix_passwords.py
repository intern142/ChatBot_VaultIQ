import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from app.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.DATABASE_URL, echo=False)
session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def fix_passwords():
    async with session_factory() as db:
        await db.execute(text("UPDATE users SET password_hash = '\$2b\$12\$s/Q.9QpLqEdyLQYDjACYvupnPY049xR9RVOdTHNcHY0qkEeincljy' WHERE email IN ('emp@polb.com', 'emp@pola.com')"))
        await db.commit()
        print('Passwords updated')

asyncio.run(fix_passwords())