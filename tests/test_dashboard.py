import uuid
from httpx import AsyncClient

async def test_dashboard_overview_requires_auth(client: AsyncClient):
    r = await client.get('/dashboard/overview')
    assert r.status_code == 401


async def test_dashboard_overview_requires_client_admin(client_admin_headers, client: AsyncClient):
    r = await client.get('/dashboard/overview', headers=client_admin_headers)
    assert r.status_code == 200


async def test_dashboard_super_admin_denied(super_admin_headers, client: AsyncClient):
    r = await client.get('/dashboard/overview', headers=super_admin_headers)
    assert r.status_code == 403
