import httpx
import json
import base64
import logging
from app.main import app

logging.disable(logging.INFO)

transport = httpx.ASGITransport(app=app)

def decode_jwt(token):
    payload = token.split(".")[1]
    payload += "=" * (4 - len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))

users = [
    ("Super Admin", "SUPER", "super@vaultiq.com", "SuperPass1!"),
    ("Client Admin", "ACME", "admin@acme.com", "AdminPass1!"),
    ("Employee", "ACME", "employee@acme.com", "StrongPass1!"),
]

import asyncio

async def run():
    client = httpx.AsyncClient(transport=transport, base_url="http://testserver")
    for name, org, email, password in users:
        resp = await client.post("/auth/login", json={
            "organisation_code": org,
            "email": email,
            "password": password,
        })
        print(f"\n=== {name} ===")
        print(f"Status: {resp.status_code}")
        claims = decode_jwt(resp.json()["access_token"])
        print(f"Claims:\n{json.dumps(claims, indent=2)}")
    await client.aclose()

asyncio.run(run())
