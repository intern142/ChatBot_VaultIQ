import asyncio
import asyncpg
from app.config import get_settings

settings = get_settings()

async def fix():
    conn = await asyncpg.connect(settings.DATABASE_URL.replace('+asyncpg', ''))
    hash_val = "$2b$12$VUGbReejUP9vX1CNUsivsOQePecEfNwqrkp5JWdW..e7VCC6bz.AG"
    await conn.execute(
        "UPDATE users SET password_hash = $1 WHERE email = $2",
        hash_val, "u2@pol.com"
    )
    await conn.execute(
        "UPDATE users SET password_hash = $1 WHERE email = $2",
        hash_val, "u1@pol.com"
    )
    print('Client admin passwords fixed')
    rows = await conn.fetch('SELECT email, password_hash FROM users WHERE role = $1', 'client_admin')
    for r in rows:
        print(f'{r["email"]}: {r["password_hash"]}')
    await conn.close()

asyncio.run(fix())