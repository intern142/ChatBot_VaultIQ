import asyncio
import asyncpg
from app.config import get_settings

settings = get_settings()

async def fix():
    conn = await asyncpg.connect(settings.DATABASE_URL.replace('+asyncpg', ''))
    # Use parameterized query to avoid escaping issues
    await conn.execute(
        "UPDATE users SET password_hash = $1 WHERE email = $2",
        "$2b$12$s/Q.9QpLqEdyLQYDjACYvupnPY049xR9RVOdTHNcHY0qkEeincljy",
        "emp@polb.com"
    )
    await conn.execute(
        "UPDATE users SET password_hash = $1 WHERE email = $2",
        "$2b$12$s/Q.9QpLqEdyLQYDjACYvupnPY049xR9RVOdTHNcHY0qkEeincljy",
        "emp@pola.com"
    )
    print('Passwords fixed')
    rows = await conn.fetch('SELECT email, password_hash FROM users WHERE email IN ($1, $2)', 'emp@polb.com', 'emp@pola.com')
    for r in rows:
        print(f'{r["email"]}: {r["password_hash"]}')
    await conn.close()

asyncio.run(fix())