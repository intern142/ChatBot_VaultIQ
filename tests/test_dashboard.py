import uuid
from httpx import AsyncClient

async def test_dashboard_overview_requires_auth(client: AsyncClient):
    r = await client.get('/dashboard/overview')
    assert r.status_code == 401


async def test_dashboard_overview_requires_client_admin(token_a_admin, client: AsyncClient):
    headers = {'Authorization': f'Bearer {token_a_admin}'}
    r = await client.get('/dashboard/overview', headers=headers)
    assert r.status_code == 200


async def test_dashboard_super_admin_denied(super_admin_token, client: AsyncClient):
    headers = {'Authorization': f'Bearer {super_admin_token}'}
    r = await client.get('/dashboard/overview', headers=headers)
    assert r.status_code == 403
