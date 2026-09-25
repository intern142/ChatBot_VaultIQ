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
    (str(uuid.uuid4()), str(uid), '')
)
conn.commit()
print(f"Created session: {sid}")

from app.auth.jwt import create_access_token
token = create_access_token(user_id=uuid.UUID(str(uid)), role='super_admin', tenant_id=None, session_id=sid)
print(f"Token created: {token[:50]}...")

conn.close()

# Test the token
from app.auth.jwt import decode_token
payload = decode_token(token)
print(f"Decoded payload: {payload}")

# Test with the app
import asyncio
import httpx
from app.main import app

async def test():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
        # First test the health endpoint
        res = await client.get('/health')
        print(f'Health: {res.status_code}, {res.json()}')
        
        # Test admin endpoint
        res = await client.post(
            '/admin/tenants',
            json={'short_code': 'TEST', 'name': 'Test', 'storage_quota_mb': 1000},
            headers={'Authorization': f'Bearer {token}'}
        )
        print(f'Admin create tenant: {res.status_code}, {res.json()}')

asyncio.run(test())