import uuid
import psycopg2
from app.config import get_settings
from app.auth.jwt import create_access_token, decode_token
from app.auth.password import hash_password

settings = get_settings()
conn = psycopg2.connect(settings.DATABASE_URL_SYNC)
conn.autocommit = False
cur = conn.cursor()
cur.execute("TRUNCATE users, tenants, sessions CASCADE")
conn.commit()

cur.execute(
    "INSERT INTO users (tenant_id, email, password_hash, role) VALUES (NULL, %s, %s, %s) RETURNING id",
    ('super@vaultiq.com', hash_password('AdminPass1!'), 'super_admin')
)
uid = cur.fetchone()[0]
print(f"Created user: {uid}")

sid = uuid.uuid4()
cur.execute(
    "INSERT INTO sessions (id, user_id, tenant_id, token_hash, expires_at) VALUES (%s, %s, NULL, %s, now() + interval '24 hours')",
    (str(sid), str(uid), '')
)
conn.commit()
print(f"Created session: {sid}")

# Verify session exists
cur.execute("SELECT * FROM sessions WHERE id = %s", (str(sid),))
row = cur.fetchone()
print(f"Session in DB: {row}")

from app.auth.jwt import create_access_token
token = create_access_token(user_id=uuid.UUID(str(uid)), role='super_admin', tenant_id=None, session_id=sid)
print(f"Token created: {token[:50]}...")

# Verify with direct SQL
cur.execute("SELECT * FROM sessions WHERE id = %s AND is_revoked = false", (str(sid),))
row = cur.fetchone()
print(f"Session check: {row}")

# Test with asyncpg directly
import asyncio
import asyncpg

async def test():
    conn = await asyncpg.connect(settings.DATABASE_URL.replace("postgresql://", "postgresql://"))
    row = await conn.fetchrow("SELECT * FROM sessions WHERE id = $1 AND is_revoked = false", sid)
    print(f"AsyncPG session check: {row}")
    await conn.close()

asyncio.run(test())
print("Done")

conn.close()