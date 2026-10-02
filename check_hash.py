import asyncio
import asyncpg
from app.config import get_settings
from app.auth.password import verify_password

settings = get_settings()

async def check():
    conn = await asyncpg.connect(settings.DATABASE_URL.replace('+asyncpg', ''))
    rows = await conn.fetch('SELECT email, password_hash FROM users WHERE email IN ($1, $2)', 'emp@polb.com', 'emp@pola.com')
    for r in rows:
        print(f'{r["email"]}: {r["password_hash"]}')
        print(f'Verify: {verify_password("StrongPass1!", r["password_hash"])}')
    await conn.close()

asyncio.run(check())