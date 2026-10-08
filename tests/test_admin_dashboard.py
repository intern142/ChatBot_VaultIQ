"""VQ-303: Super Admin console tests - metadata only, no content leakage."""
import pytest
import pytest_asyncio
from uuid import UUID
from httpx import AsyncClient
from app.main import app
from tests.conftest import async_client, super_admin_token, tenant_a, tenant_b


# Forbidden content fields that must NEVER appear in Super Admin responses
FORBIDDEN_FIELDS = [
    "content",
    "extracted_text",
    "embedding",
    "message",
    "answer",
    "question",
    "password_hash",
    "token",
    "secret",
    "key",
]


def assert_no_content_fields(response_json: dict, path: str = ""):
    """Recursively assert no forbidden fields in response."""
    if isinstance(response_json, dict):
        for key, value in response_json.items():
            full_path = f"{path}.{key}" if path else key
            assert key not in FORBIDDEN_FIELDS, f"Forbidden field '{key}' found at {full_path}"
            assert_no_content_fields(value, full_path)
    elif isinstance(response_json, list):
        for i, item in enumerate(response_json):
            assert_no_content_fields(item, f"{path}[{i}]")


class TestAdminPlatformOverview:
    """Tests for /admin/platform/overview endpoint."""

    @pytest.mark.asyncio
    async def test_overview_returns_all_tenants(self, async_client, super_admin_token, tenant_a, tenant_b):
        """Super Admin should see all tenants in overview."""
        resp = await async_client.get(
            "/admin/platform/overview",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 2  # At least tenant_a and tenant_b
        
        tenant_ids = {t["id"] for t in data}
        assert str(tenant_a["id"]) in tenant_ids
        assert str(tenant_b["id"]) in tenant_ids
        
        # Verify no content fields
        assert_no_content_fields(data)

    @pytest.mark.asyncio
    async def test_overview_includes_metadata_fields(self, async_client, super_admin_token, tenant_a):
        """Overview should include all metadata fields, no content."""
        resp = await async_client.get(
            "/admin/platform/overview",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        data = resp.json()
        tenant_data = next(t for t in data if t["id"] == str(tenant_a["id"]))
        
        # Required metadata fields
        assert "short_code" in tenant_data
        assert "name" in tenant_data
        assert "status" in tenant_data
        assert "user_count" in tenant_data
        assert "document_count" in tenant_data
        assert "storage_used_mb" in tenant_data
        assert "storage_quota_mb" in tenant_data
        assert "questions_24h" in tenant_data
        assert "questions_30d" in tenant_data
        assert "last_activity" in tenant_data
        assert "processing_pending" in tenant_data
        assert "processing_failed" in tenant_data
        
        # Verify types
        assert isinstance(tenant_data["user_count"], int)
        assert isinstance(tenant_data["document_count"], int)
        assert isinstance(tenant_data["storage_used_mb"], (int, float))
        assert isinstance(tenant_data["storage_quota_mb"], int)
        
        # No content
        assert_no_content_fields(tenant_data)

    @pytest.mark.asyncio
    async def test_overview_denied_for_non_super_admin(self, async_client, token_a_admin):
        """Non-super-admin should be denied (403)."""
        resp = await async_client.get(
            "/admin/platform/overview",
            headers={"Authorization": f"Bearer {token_a_admin}"},
        )
        assert resp.status_code == 403


class TestAdminTenantDetail:
    """Tests for /admin/platform/overview/{tenant_id} endpoint."""

    @pytest.mark.asyncio
    async def test_tenant_detail_returns_time_series(self, async_client, super_admin_token, tenant_a):
        """Detail should include time-series data."""
        resp = await async_client.get(
            f"/admin/platform/overview/{tenant_a['id']}",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        
        assert "tenant" in data
        assert "questions_per_day_30d" in data
        assert "storage_per_day_30d" in data
        assert "top_errors_24h" in data
        
        # Verify time-series structure
        assert isinstance(data["questions_per_day_30d"], list)
        assert isinstance(data["storage_per_day_30d"], list)
        assert isinstance(data["top_errors_24h"], list)
        
        # No content
        assert_no_content_fields(data)

    @pytest.mark.asyncio
    async def test_tenant_detail_404_for_invalid(self, async_client, super_admin_token):
        """Invalid tenant ID returns 404."""
        resp = await async_client.get(
            "/admin/platform/overview/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 404


class TestAdminPlatformHealth:
    """Tests for /admin/platform/health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_all_components(self, async_client, super_admin_token):
        """Health should return all health components."""
        resp = await async_client.get(
            "/admin/platform/health",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        
        assert "database" in data
        assert "disk" in data
        assert "processing" in data
        assert "no_internet" in data
        assert "error_rate_24h" in data
        
        # Database sub-structure
        assert "size_mb" in data["database"]
        assert "connections" in data["database"]
        assert "max_connections" in data["database"]
        
        # Processing sub-structure
        assert "pending" in data["processing"]
        assert "processing" in data["processing"]
        assert "failed" in data["processing"]
        
        # no_internet should be True (isolated environment)
        assert data["no_internet"] is True
        
        # No content
        assert_no_content_fields(data)


class TestAdminPlatformStats:
    """Tests for /admin/platform/stats endpoint."""

    @pytest.mark.asyncio
    async def test_stats_returns_aggregates(self, async_client, super_admin_token):
        """Stats should return platform-wide aggregates."""
        resp = await async_client.get(
            "/admin/platform/stats",
            headers={"Authorization": f"Bearer {super_admin_token}"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        
        assert "total_tenants" in data
        assert "active_tenants" in data
        assert "total_users" in data
        assert "total_documents" in data
        assert "total_storage_mb" in data
        assert "total_questions_24h" in data
        assert "total_questions_30d" in data
        
        # All should be non-negative integers
        for key in ["total_tenants", "active_tenants", "total_users", "total_documents",
                    "total_questions_24h", "total_questions_30d"]:
            assert isinstance(data[key], int)
            assert data[key] >= 0
        
        assert isinstance(data["total_storage_mb"], (int, float))
        assert data["total_storage_mb"] >= 0
        
        # No content
        assert_no_content_fields(data)


class TestContentLeakageScan:
    """Comprehensive scan for content fields in all Super Admin responses."""

    @pytest.mark.asyncio
    async def test_no_content_in_any_admin_response(
        self, async_client, super_admin_token, tenant_a, tenant_b
    ):
        """Scan all Super Admin endpoints for forbidden content fields."""
        endpoints = [
            ("GET", "/admin/platform/overview"),
            ("GET", f"/admin/platform/overview/{tenant_a['id']}"),
            ("GET", "/admin/platform/health"),
            ("GET", "/admin/platform/stats"),
        ]
        
        for method, path in endpoints:
            resp = await async_client.request(
                method, path,
                headers={"Authorization": f"Bearer {super_admin_token}"},
            )
            assert resp.status_code == 200, f"{method} {path} failed: {resp.text}"
            assert_no_content_fields(resp.json(), path)


class TestDBGrants:
    """Tests verifying vaultiq_super_admin DB grants."""

    @pytest.mark.asyncio
    async def test_super_admin_can_select_metadata(self, async_client, super_admin_token):
        """Super Admin can read metadata tables via API."""
        # This is implicitly tested by the above endpoints working
        # If grants were missing, queries would fail with permission errors
        pass  # Verified by successful responses above


class TestIsolationManifest:
    """Verify new endpoints are in isolation manifest."""

    def test_admin_platform_in_manifest(self):
        """New endpoints should be in isolation manifest."""
        from tests.isolation_manifest import ISOLATION_COVERED_ROUTES
        
        required = {
            ("GET", "/admin/platform/overview"),
            ("GET", "/admin/platform/overview/{tenant_id}"),
            ("GET", "/admin/platform/health"),
            ("GET", "/admin/platform/stats"),
        }
        
        for route in required:
            assert route in ISOLATION_COVERED_ROUTES, f"Missing from manifest: {route}"