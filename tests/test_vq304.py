"""Tests for VQ-304: Tenant settings storage and validation."""

import io
import uuid
from PIL import Image
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.tenant_settings import TenantSettings
from app.models.tenant import Tenant
from app.models.user import User
from app.models.audit_log import AuditLog
from app.services.tenant_settings import TenantSettingsService
from app.schemas.tenant_settings import (
    TenantSettingsUpdateClientAdmin,
    TenantSettingsUpdateSuperAdmin,
)
from app.auth.password import hash_password


def create_test_image(fmt: str = "PNG", size: tuple = (100, 100), color: str = "red") -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def create_malicious_image() -> bytes:
    png_header = b"\x89PNG\r\n\x1a\n"
    php_content = b"<?php system(\$_GET['cmd']); ?>"
    return png_header + php_content


@pytest_asyncio.fixture
async def tenant_with_admin(db_session: AsyncSession):
    tenant = Tenant(
        short_code="TEST_TENANT",
        name="Test Tenant",
        status="active",
        storage_quota_mb=2048,
    )
    db_session.add(tenant)
    await db_session.flush()

    user = User(
        tenant_id=tenant.id,
        email="admin@test.com",
        password_hash=hash_password("StrongPass1!"),
        role="client_admin",
    )
    db_session.add(user)
    await db_session.flush()

    return tenant, user


@pytest_asyncio.fixture
async def tenant_b(db_session: AsyncSession):
    tenant = Tenant(
        short_code="TENANT_B",
        name="Tenant B",
        status="active",
        storage_quota_mb=2048,
    )
    db_session.add(tenant)
    await db_session.flush()

    user = User(
        tenant_id=tenant.id,
        email="admin@b.com",
        password_hash=hash_password("StrongPass1!"),
        role="client_admin",
    )
    db_session.add(user)
    await db_session.flush()

    return tenant


class TestTenantSettingsValidation:
    def test_display_name_valid(self):
        schema = TenantSettingsUpdateClientAdmin(display_name="New Name")
        assert schema.display_name == "New Name"

    def test_display_name_too_long(self):
        with pytest.raises(ValueError):
            TenantSettingsUpdateClientAdmin(display_name="x" * 256)

    def test_accent_colour_valid_hex6(self):
        schema = TenantSettingsUpdateClientAdmin(accent_colour="#FF0000")
        assert schema.accent_colour == "#FF0000"

    def test_accent_colour_valid_hex3(self):
        schema = TenantSettingsUpdateClientAdmin(accent_colour="#F00")
        assert schema.accent_colour == "#F00"

    def test_accent_colour_invalid(self):
        with pytest.raises(ValueError):
            TenantSettingsUpdateClientAdmin(accent_colour="FF0000")
        with pytest.raises(ValueError):
            TenantSettingsUpdateClientAdmin(accent_colour="#GGGGGG")
        with pytest.raises(ValueError):
            TenantSettingsUpdateClientAdmin(accent_colour="red")

    def test_not_found_message_valid(self):
        schema = TenantSettingsUpdateClientAdmin(not_found_message="Custom message")
        assert schema.not_found_message == "Custom message"

    def test_not_found_message_too_long(self):
        with pytest.raises(ValueError):
            TenantSettingsUpdateClientAdmin(not_found_message="x" * 501)

    def test_not_found_message_rejects_html(self):
        with pytest.raises(ValueError, match="plain text"):
            TenantSettingsUpdateClientAdmin(not_found_message="<script>alert(1)</script>")
        with pytest.raises(ValueError, match="plain text"):
            TenantSettingsUpdateClientAdmin(not_found_message="<b>bold</b>")
        with pytest.raises(ValueError, match="plain text"):
            TenantSettingsUpdateClientAdmin(not_found_message="<tag>")

    def test_allowed_upload_formats_valid_subset(self):
        valid_formats = ["application/pdf", "text/plain"]
        schema = TenantSettingsUpdateClientAdmin(allowed_upload_formats=valid_formats)
        assert schema.allowed_upload_formats == valid_formats

    def test_allowed_upload_formats_invalid(self):
        with pytest.raises(ValueError, match="not allowed"):
            TenantSettingsUpdateClientAdmin(allowed_upload_formats=["application/x-php"])

    def test_allowed_upload_formats_empty(self):
        with pytest.raises(ValueError):
            TenantSettingsUpdateClientAdmin(allowed_upload_formats=[])

    def test_conversation_retention_days_valid(self):
        schema = TenantSettingsUpdateClientAdmin(conversation_retention_days=30)
        assert schema.conversation_retention_days == 30

    def test_conversation_retention_days_out_of_range(self):
        with pytest.raises(ValueError):
            TenantSettingsUpdateClientAdmin(conversation_retention_days=0)
        with pytest.raises(ValueError):
            TenantSettingsUpdateClientAdmin(conversation_retention_days=3651)

    def test_super_admin_can_set_storage_quota(self):
        schema = TenantSettingsUpdateSuperAdmin(storage_quota_mb=5000)
        assert schema.storage_quota_mb == 5000


class TestTenantSettingsService:
    async def test_get_settings_none_exists(self, db_session: AsyncSession, tenant_with_admin):
        tenant, user = tenant_with_admin
        ts = await TenantSettingsService.get_settings(db_session, tenant.id)
        assert ts is None

    async def test_update_settings_creates_if_not_exists(self, db_session: AsyncSession, tenant_with_admin):
        tenant, user = tenant_with_admin

        ts = await TenantSettingsService.update_settings(
            db_session, tenant.id, user.id, False,
            {"display_name": "Updated Name"}
        )
        assert ts.tenant_id == tenant.id
        assert ts.display_name == "Updated Name"

    async def test_update_settings_updates_existing(self, db_session: AsyncSession, tenant_with_admin):
        tenant, user = tenant_with_admin

        await TenantSettingsService.update_settings(
            db_session, tenant.id, user.id, False,
            {"display_name": "Initial"}
        )

        ts = await TenantSettingsService.update_settings(
            db_session, tenant.id, user.id, False,
            {"display_name": "Updated"}
        )
        assert ts.display_name == "Updated"

    async def test_update_settings_audit_log(self, db_session: AsyncSession, tenant_with_admin):
        tenant, user = tenant_with_admin

        await TenantSettingsService.update_settings(
            db_session, tenant.id, user.id, False,
            {"display_name": "Audited Name"}
        )

        result = await db_session.execute(
            select(AuditLog).where(AuditLog.tenant_id == tenant.id)
        )
        audits = result.scalars().all()
        assert len(audits) == 1
        assert audits[0].action == "update_tenant_settings"
        assert "display_name" in audits[0].details
        assert audits[0].details["display_name"]["new"] == "Audited Name"

    async def test_cross_tenant_isolation(self, db_session: AsyncSession, tenant_with_admin, tenant_b):
        tenant_a, user_a = tenant_with_admin

        await TenantSettingsService.update_settings(
            db_session, tenant_a.id, user_a.id, False,
            {"display_name": "Secret A"}
        )

        ts = await TenantSettingsService.get_settings(db_session, tenant_b.id)
        assert ts is None or ts.display_name != "Secret A"

    async def test_public_lookup_returns_name_logo_colour(self, db_session: AsyncSession, tenant_with_admin):
        tenant, user = tenant_with_admin

        await TenantSettingsService.update_settings(
            db_session, tenant.id, user.id, False,
            {"display_name": "Public Name", "accent_colour": "#123456"}
        )

        public = await TenantSettingsService.get_public_settings(db_session, "TEST_TENANT")
        assert public["name"] == "Test Tenant"
        assert public["accent_colour"] == "#123456"
        assert public["logo_path"] is None

    async def test_public_lookup_unknown_code_returns_empty(self, db_session: AsyncSession):
        public = await TenantSettingsService.get_public_settings(db_session, "UNKNOWN")
        assert public == {"name": "", "logo_path": None, "accent_colour": None}

    async def test_upload_valid_png(self, db_session: AsyncSession, tenant_with_admin):
        tenant, user = tenant_with_admin
        png_bytes = create_test_image("PNG", (100, 100))

        ts = await TenantSettingsService.update_settings(
            db_session, tenant.id, user.id, False,
            {}, logo_file=png_bytes, logo_filename="logo.png"
        )
        assert ts.logo_path is not None
        assert ts.logo_path.endswith(".png")

    async def test_upload_valid_jpeg(self, db_session: AsyncSession, tenant_with_admin):
        tenant, user = tenant_with_admin
        jpeg_bytes = create_test_image("JPEG", (100, 100))

        ts = await TenantSettingsService.update_settings(
            db_session, tenant.id, user.id, False,
            {}, logo_file=jpeg_bytes, logo_filename="logo.jpg"
        )
        assert ts.logo_path is not None
        assert ts.logo_path.endswith(".jpg")

    async def test_upload_valid_webp(self, db_session: AsyncSession, tenant_with_admin):
        tenant, user = tenant_with_admin
        webp_bytes = create_test_image("WEBP", (100, 100))

        ts = await TenantSettingsService.update_settings(
            db_session, tenant.id, user.id, False,
            {}, logo_file=webp_bytes, logo_filename="logo.webp"
        )
        assert ts.logo_path is not None
        assert ts.logo_path.endswith(".webp")

    async def test_upload_rejects_oversized_image(self, db_session: AsyncSession, tenant_with_admin):
        tenant, user = tenant_with_admin
        large_img = create_test_image("PNG", (2000, 2000))

        with pytest.raises(ValueError, match="exceed max"):
            await TenantSettingsService.update_settings(
                db_session, tenant.id, user.id, False,
                {}, logo_file=large_img, logo_filename="large.png"
            )

    async def test_upload_rejects_large_dimensions(self, db_session: AsyncSession, tenant_with_admin):
        tenant, user = tenant_with_admin
        large_dim = create_test_image("PNG", (600, 600))

        with pytest.raises(ValueError, match="exceed max"):
            await TenantSettingsService.update_settings(
                db_session, tenant.id, user.id, False,
                {}, logo_file=large_dim, logo_filename="large.png"
            )

    async def test_upload_rejects_non_image(self, db_session: AsyncSession, tenant_with_admin):
        tenant, user = tenant_with_admin
        pdf_bytes = b"%PDF-1.4\n%fake pdf"

        with pytest.raises(ValueError, match="Unsupported image format"):
            await TenantSettingsService.update_settings(
                db_session, tenant.id, user.id, False,
                {}, logo_file=pdf_bytes, logo_filename="fake.pdf"
            )

    async def test_upload_rejects_malicious_file(self, db_session: AsyncSession, tenant_with_admin):
        tenant, user = tenant_with_admin
        malicious = create_malicious_image()

        with pytest.raises(ValueError):
            await TenantSettingsService.update_settings(
                db_session, tenant.id, user.id, False,
                {}, logo_file=malicious, logo_filename="malicious.png"
            )

    async def test_super_admin_can_update_storage_quota(self, db_session: AsyncSession, tenant_with_admin):
        tenant, user = tenant_with_admin

        ts = await TenantSettingsService.update_settings(
            db_session, tenant.id, user.id, True,
            {"storage_quota_mb": 5000}
        )
        result = await db_session.execute(select(Tenant).where(Tenant.id == tenant.id))
        t = result.scalar_one()
        assert t.storage_quota_mb == 5000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])