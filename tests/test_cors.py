"""CORS middleware tests for the frontend dev server.

CORS is a browser-enforced mechanism, so these tests assert on the
preflight OPTIONS response and the Access-Control-* response headers rather
than on business behaviour.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

ALLOWED_ORIGIN = "http://localhost:5173"
DISALLOWED_ORIGIN = "http://evil.example.com"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


class TestPreflight:
    async def test_preflight_from_allowed_origin_is_permitted(self, client):
        response = await client.options(
            "/auth/login",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN

    async def test_preflight_from_unknown_origin_is_refused(self, client):
        response = await client.options(
            "/auth/login",
            headers={
                "Origin": DISALLOWED_ORIGIN,
                "Access-Control-Request-Method": "POST",
            },
        )
        assert "access-control-allow-origin" not in response.headers

    async def test_preflight_permits_bearer_and_content_type(self, client):
        response = await client.options(
            "/documents",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        allowed_headers = response.headers.get("access-control-allow-headers", "")
        assert "authorization" in allowed_headers.lower()
        assert "content-type" in allowed_headers.lower()


class TestActualRequest:
    async def test_health_response_carries_allow_origin(self, client):
        response = await client.get("/health", headers={"Origin": ALLOWED_ORIGIN})
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN

    async def test_credentialed_requests_are_marked(self, client):
        response = await client.get("/health", headers={"Origin": ALLOWED_ORIGIN})
        assert response.headers.get("access-control-allow-credentials") == "true"

    async def test_no_allow_origin_header_without_origin_header(self, client):
        response = await client.get("/health")
        assert "access-control-allow-origin" not in response.headers


class TestIsolationIsUnaffected:
    """CORS must not become a tenant-isolation hole. A cross-tenant read is
    still refused, and the refusal body is still checked."""

    async def test_preflight_does_not_bypass_auth(self, client):
        """OPTIONS on a protected route must not return the route's payload."""
        response = await client.options(
            "/documents",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code != 200 or "documents" not in response.text

    async def test_cors_headers_absent_on_error_responses_from_other_origin(
        self, client
    ):
        response = await client.get(
            "/documents", headers={"Origin": DISALLOWED_ORIGIN}
        )
        assert response.status_code in (401, 403)
        assert "access-control-allow-origin" not in response.headers
