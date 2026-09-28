"""Super Admin platform access under RLS - Known Defect #2.

Before this module, the suite carried 17 failures and 1 error that all traced
back to one cause: platform accounts have tenant_id IS NULL (VQ-101 AC3), and the
policies on users and sessions had no branch for that case. Under vaultiq_app -
the production identity - a Super Admin login returned 401 and writing a
platform session row was rejected outright, so tenant lifecycle could not be
exercised at all.

These tests connect as vaultiq_app (NOBYPASSRLS) and assert the three
properties the fix is supposed to guarantee, in both directions:

  1. A Super Admin can authenticate and use platform endpoints.
  2. A tenant can neither see nor become a platform account, and a platform
     request cannot see tenant content.
  3. Every combination of the two context settings fails closed rather than
     erroring or widening.

Test 2 matters more than test 1. A fix that makes Super Admin work by
loosening the tenant policy would pass test 1 and break the product.
"""

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.auth.jwt import create_access_token
from app.auth.password import hash_password

PLATFORM_EMAIL = "super@vaultiq.com"
PLATFORM_PASSWORD = "AdminPass1!"


# Function-scoped: seed platform user via admin identity (BYPASSRLS) for each test.
# The admin identity truncates on setup, so we re-seed every time.
@pytest_asyncio.fixture(scope="function")
async def platform_user_id(db_engine):
    """A Super Admin row with no tenant, seeded as the admin identity."""
    async with db_engine.begin() as conn:
        result = await conn.execute(
            text("""
                INSERT INTO users (tenant_id, email, password_hash, role)
                VALUES (NULL, :email, :ph, 'super_admin')
                RETURNING id
            """),
            {"email": PLATFORM_EMAIL, "ph": hash_password(PLATFORM_PASSWORD)},
        )
        uid = result.scalar()
    yield uid
    # No cleanup: db_engine truncates on next test's setup, and the user is re-seeded.
    # Cleanup would fail due to audit_log FK from tenant creation in tests.


@pytest_asyncio.fixture(scope="function")
async def app_session(app_db_engine):
    """Session on the app identity (vaultiq_app), NOBYPASSRLS, no truncate.

    Built from app_db_engine fixture rather than the application's
    AsyncSessionLocal, because the latter is wired to settings.DATABASE_URL -
    the superuser. Reusing it here would silently make every assertion below
    vacuous, which is precisely the trap this module exists to close.
    """
    factory = async_sessionmaker(
        app_db_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        yield session


def _new_app_session(app_db_engine):
    """Create a fresh session for cross-fixture visibility.

    The app_session fixture opens a transaction at setup time, which takes a
    snapshot that won't include data committed by other fixtures (e.g.
    platform_token's login). Call this to get a session that sees the latest
    committed state.
    """
    factory = async_sessionmaker(
        app_db_engine, class_=AsyncSession, expire_on_commit=False
    )
    return factory()


@pytest_asyncio.fixture(scope="function")
async def platform_token(async_client, platform_user_id):
    """A live Super Admin session obtained via the real login endpoint.

    Uses the async_client fixture (which has the app identity override) so the
    login runs under vaultiq_app with RLS enforced.
    """
    resp = await async_client.post(
        "/auth/login",
        json={
            "organisation_code": "SUPER",
            "email": PLATFORM_EMAIL,
            "password": PLATFORM_PASSWORD,
        },
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


class TestSuperAdminCanAuthenticate:
    """Property 1: the platform identity is reachable under its own context."""

    @pytest.mark.asyncio
    async def test_super_admin_login_succeeds(self, platform_token):
        assert platform_token is not None

    @pytest.mark.asyncio
    async def test_super_admin_token_has_no_tenant(self, platform_token):
        from app.auth.jwt import decode_token
        payload = decode_token(platform_token)
        assert payload["role"] == "super_admin"
        assert payload.get("tenant_id") is None

    @pytest.mark.asyncio
    async def test_super_admin_can_create_a_tenant(self, platform_token, async_client):
        resp = await async_client.post(
            "/admin/tenants",
            json={"short_code": "PLAT", "name": "Platform Test Co", "storage_quota_mb": 128},
            headers={"Authorization": f"Bearer {platform_token}"},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["short_code"] == "PLAT"

    @pytest.mark.asyncio
    async def test_super_admin_can_list_tenants(self, platform_token, async_client, tenant_a):
        resp = await async_client.get(
            "/admin/tenants", headers={"Authorization": f"Bearer {platform_token}"}
        )
        assert resp.status_code == 200, resp.text
        assert any(t["short_code"] == "TENANT_A" for t in resp.json())

    @pytest.mark.asyncio
    async def test_super_admin_refresh_works(self, platform_token, async_client):
        resp = await async_client.post(
            "/auth/refresh", headers={"Authorization": f"Bearer {platform_token}"}
        )
        assert resp.status_code == 200, resp.text

    @pytest.mark.asyncio
    async def test_super_admin_logout_revokes(self, platform_token, async_client):
        resp = await async_client.post(
            "/auth/logout", headers={"Authorization": f"Bearer {platform_token}"}
        )
        assert resp.status_code == 200, resp.text
        after = await async_client.post(
            "/auth/refresh", headers={"Authorization": f"Bearer {platform_token}"}
        )
        assert after.status_code == 401


class TestPlatformCannotSeeTenantContent:
    """Property 2a: the platform context must not widen into tenant data.

    This is the direction that would end the business. Rule #1 is that a tenant
    cannot reach another tenant; the mirror risk introduced by a platform-access
    policy is that Super Admin, who can create and suspend every tenant, could
    read their documents and questions. VQ-106 already denies Super Admin on
    /documents/*, and these tests confirm the *database* would refuse too, so
    the guarantee does not rest on the permission matrix alone.
    """

    @pytest.mark.asyncio
    async def test_super_admin_is_denied_documents(self, platform_token, async_client, doc_a):
        for method, path in [
            ("GET", "/documents"),
            ("GET", "/documents/usage"),
            ("GET", f"/documents/{doc_a['id']}/preview"),
            ("GET", f"/documents/{doc_a['id']}/download"),
            ("DELETE", f"/documents/{doc_a['id']}"),
        ]:
            resp = await async_client.request(
                method, path, headers={"Authorization": f"Bearer {platform_token}"}
            )
            assert resp.status_code == 403, f"{method} {path} -> {resp.status_code}"

    @pytest.mark.asyncio
    async def test_platform_context_sees_no_tenant_users(self, app_session, platform_user_id, tenant_a):
        await app_session.execute(text("SELECT set_config('app.current_tenant', '', true)"))
        await app_session.execute(text("SELECT set_config('app.platform_access', 'on', true)"))
        result = await app_session.execute(
            text("SELECT count(*) FROM users WHERE tenant_id IS NOT NULL")
        )
        assert result.scalar() == 0

    @pytest.mark.asyncio
    async def test_platform_context_sees_no_tenant_documents(self, app_session, platform_user_id, doc_a):
        await app_session.execute(text("SELECT set_config('app.current_tenant', '', true)"))
        await app_session.execute(text("SELECT set_config('app.platform_access', 'on', true)"))
        result = await app_session.execute(text("SELECT count(*) FROM documents"))
        assert result.scalar() == 0

    @pytest.mark.asyncio
    async def test_platform_context_sees_no_audit_rows(self, app_session, platform_user_id, tenant_a):
        await app_session.execute(text("SELECT set_config('app.current_tenant', '', true)"))
        await app_session.execute(text("SELECT set_config('app.platform_access', 'on', true)"))
        result = await app_session.execute(text("SELECT count(*) FROM audit_logs"))
        assert result.scalar() == 0

    @pytest.mark.asyncio
    async def test_platform_context_sees_only_platform_rows(self, app_session, platform_user_id, tenant_a):
        await app_session.execute(text("SELECT set_config('app.current_tenant', '', true)"))
        await app_session.execute(text("SELECT set_config('app.platform_access', 'on', true)"))
        total = await app_session.execute(text("SELECT count(*) FROM users"))
        platform = await app_session.execute(
            text("SELECT count(*) FROM users WHERE tenant_id IS NULL")
        )
        assert platform.scalar() == 1
        assert total.scalar() == 1

    @pytest.mark.asyncio
    async def test_platform_sessions_exclude_tenant_sessions(self, platform_token, app_db_engine):
        """Test without token_a_admin to isolate the session creation."""
        factory = async_sessionmaker(
            app_db_engine, class_=AsyncSession, expire_on_commit=False
        )
        db = factory()
        try:
            await db.execute(text("SELECT set_config('app.current_tenant', '', true)"))
            await db.execute(text("SELECT set_config('app.platform_access', 'on', true)"))
            total = (await db.execute(text("SELECT count(*) FROM sessions"))).scalar()
            platform = (await db.execute(text("SELECT count(*) FROM sessions WHERE tenant_id IS NULL"))).scalar()
            assert platform >= 1
            assert total == platform
        finally:
            await db.close()


class TestTenantCannotBecomePlatform:
    """Property 2b: a tenant must not be able to reach or forge a platform row.

    Note these are the negative cases. A fix that widened the tenant policy
    instead of adding a gated one would leave the positive Super Admin tests
    green while failing these.
    """

    @pytest.mark.asyncio
    async def test_tenant_context_cannot_see_platform_user(self, app_session, platform_user_id, token_a_admin):
        await app_session.execute(
            text("SELECT set_config('app.current_tenant', :t, true)"),
            {"t": "006f5d34-2133-4b75-9711-6c04a60be77b"},
        )
        visible = await app_session.execute(
            text("SELECT count(*) FROM users WHERE tenant_id IS NULL")
        )
        assert visible.scalar() == 0

    @pytest.mark.asyncio
    async def test_platform_flag_does_not_help_a_tenant_token(
        self, app_session, platform_user_id, token_a_admin
    ):
        """A tenant token with app.platform_access forced on still reads nothing.

        apply_token_context decides the context from the token. This asserts the
        opposite direction of that decision: even when both settings are
        present, the platform policy requires no tenant in context, so the two
        cannot be combined into a context that sees everything.
        """
        await app_session.execute(
            text("SELECT set_config('app.current_tenant', :t, true)"),
            {"t": "006f5d34-2133-4b75-9711-6c04a60be77b"},
        )
        await app_session.execute(text("SELECT set_config('app.platform_access', 'on', true)"))
        platform = await app_session.execute(
            text("SELECT count(*) FROM users WHERE tenant_id IS NULL")
        )
        assert platform.scalar() == 0

    @pytest.mark.asyncio
    async def test_app_cannot_insert_a_platform_user_without_context(self, app_session, platform_user_id):
        from sqlalchemy.exc import DBAPIError

        with pytest.raises(DBAPIError):
            await app_session.execute(
                text("""
                    INSERT INTO users (email, password_hash, role, tenant_id)
                    VALUES ('sneaky@vaultiq.local', 'x', 'super_admin', NULL)
                """)
            )

    @pytest.mark.asyncio
    async def test_app_cannot_insert_platform_user_with_tenant_context(self, app_session, platform_user_id, tenant_a):
        """The tenant context must not authorise creating a platform account."""
        from sqlalchemy.exc import DBAPIError

        await app_session.execute(
            text("SELECT set_config('app.current_tenant', :t, true)"),
            {"t": "006f5d34-2133-4b75-9711-6c04a60be77b"},
        )
        with pytest.raises(DBAPIError):
            await app_session.execute(
                text("""
                    INSERT INTO users (email, password_hash, role, tenant_id)
                    VALUES ('sneaky2@vaultiq.local', 'x', 'super_admin', NULL)
                """)
            )

    @pytest.mark.asyncio
    async def test_tenant_cannot_see_platform_audit_trail(self, app_session, platform_user_id, tenant_a):
        await app_session.execute(
            text("SELECT set_config('app.current_tenant', :t, true)"),
            {"t": "006f5d34-2133-4b75-9711-6c04a60be77b"},
        )
        platform = await app_session.execute(
            text("SELECT count(*) FROM audit_logs WHERE tenant_id IS NULL")
        )
        assert platform.scalar() == 0


class TestContextFailsClosed:
    """Property 3: no context combination may error or widen.

    The migration had to rewrite tenant_isolation as well, because casting '' to
    uuid raised "invalid input syntax" on a platform request. These assert the
    absent and empty cases return zero rows instead of raising, which is the
    same defect class as the missing_ok bug fixed on documents.
    """

    @pytest.mark.asyncio
    async def test_no_context_at_all_returns_zero_rows(self, app_session, platform_user_id, tenant_a):
        result = await app_session.execute(text("SELECT count(*) FROM users"))
        assert result.scalar() == 0

    @pytest.mark.asyncio
    async def test_empty_tenant_context_does_not_raise(self, app_session, platform_user_id, tenant_a):
        await app_session.execute(text("SELECT set_config('app.current_tenant', '', true)"))
        result = await app_session.execute(text("SELECT count(*) FROM users"))
        assert result.scalar() == 0

    @pytest.mark.asyncio
    async def test_empty_tenant_context_on_documents_does_not_raise(
        self, app_session, platform_user_id, doc_a
    ):
        """Regression guard for the cast bug on a platform-shaped request."""
        await app_session.execute(text("SELECT set_config('app.current_tenant', '', true)"))
        result = await app_session.execute(text("SELECT count(*) FROM documents"))
        assert result.scalar() == 0

    @pytest.mark.asyncio
    async def test_empty_tenant_context_on_audit_logs_does_not_raise(
        self, app_session, platform_user_id, tenant_a
    ):
        await app_session.execute(text("SELECT set_config('app.current_tenant', '', true)"))
        result = await app_session.execute(text("SELECT count(*) FROM audit_logs"))
        assert result.scalar() == 0

    @pytest.mark.asyncio
    async def test_platform_flag_alone_without_super_admin_rows(
        self, app_session, tenant_a, token_a_admin
    ):
        """The flag grants nothing on its own; rows must still be platform rows."""
        await app_session.execute(text("SELECT set_config('app.current_tenant', '', true)"))
        await app_session.execute(text("SELECT set_config('app.platform_access', 'on', true)"))
        result = await app_session.execute(text("SELECT count(*) FROM users"))
        assert result.scalar() == 0


class TestAppRoleCannotBypass:
    """The fix must not have granted BYPASSRLS or ownership to the app role."""

    @pytest.mark.asyncio
    async def test_app_role_has_no_bypassrls(self, app_session):
        result = await app_session.execute(
            text("SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = 'vaultiq_app'")
        )
        bypass, superuser = result.one()
        assert bypass is False
        assert superuser is False

    @pytest.mark.asyncio
    async def test_platform_policy_exists_on_both_tables(self, app_session):
        result = await app_session.execute(
            text("""
                SELECT tablename FROM pg_policies
                WHERE policyname = 'platform_account_access'
            """)
        )
        assert {r[0] for r in result} == {"users", "sessions"}

    @pytest.mark.asyncio
    async def test_tenant_policy_still_present_on_all_scoped_tables(self, app_session):
        """Rewriting tenant_isolation for the cast must not have dropped it."""
        result = await app_session.execute(
            text("""
                SELECT tablename FROM pg_policies
                WHERE policyname = 'tenant_isolation'
            """)
        )
        assert {r[0] for r in result} == {
            "users",
            "sessions",
            "documents",
            "invites",
            "audit_logs",
        }