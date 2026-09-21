import pytest
import uuid
import psycopg2
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.tenant import Tenant
from app.models.user import User
from app.models.session import Session
from app.config import get_settings

settings = get_settings()


def get_admin_connection():
    return psycopg2.connect(settings.DATABASE_URL_SYNC)


def get_app_connection():
    app_url = settings.DATABASE_URL_SYNC.replace("vaultiq:vaultiq_secret", "vaultiq_app:vaultiq_secret")
    return psycopg2.connect(app_url)


def get_super_admin_connection():
    super_url = settings.DATABASE_URL_SYNC.replace("vaultiq:vaultiq_secret", "vaultiq_super_admin:vaultiq_secret")
    return psycopg2.connect(super_url)


@pytest.fixture
def two_tenants():
    """Create two tenants and return their IDs."""
    conn = get_admin_connection()
    cur = conn.cursor()
    cur.execute("TRUNCATE sessions, users, tenants CASCADE")
    conn.commit()

    cur.execute("INSERT INTO tenants (short_code, name) VALUES (%s, %s) RETURNING id", ("TENANT1", "Tenant One"))
    tenant1_id = cur.fetchone()[0]

    cur.execute("INSERT INTO tenants (short_code, name) VALUES (%s, %s) RETURNING id", ("TENANT2", "Tenant Two"))
    tenant2_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()
    return str(tenant1_id), str(tenant2_id)


@pytest.fixture
def tenant_data(two_tenants):
    """Create users and sessions for two tenants."""
    tenant1_id, tenant2_id = two_tenants
    conn = get_admin_connection()
    cur = conn.cursor()

    # Tenant 1 user and session
    cur.execute(
        "INSERT INTO users (tenant_id, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
        (tenant1_id, "user1@tenant1.com", "hash1", "employee"),
    )
    user1_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO sessions (user_id, tenant_id, token_hash, expires_at) VALUES (%s, %s, %s, NOW() + INTERVAL '1 hour') RETURNING id",
        (user1_id, tenant1_id, "token_hash_1"),
    )
    session1_id = cur.fetchone()[0]

    # Tenant 2 user and session
    cur.execute(
        "INSERT INTO users (tenant_id, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id",
        (tenant2_id, "user2@tenant2.com", "hash2", "employee"),
    )
    user2_id = cur.fetchone()[0]

    cur.execute(
        "INSERT INTO sessions (user_id, tenant_id, token_hash, expires_at) VALUES (%s, %s, %s, NOW() + INTERVAL '1 hour') RETURNING id",
        (user2_id, tenant2_id, "token_hash_2"),
    )
    session2_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    return {
        "tenant1_id": tenant1_id,
        "tenant2_id": tenant2_id,
        "user1_id": str(user1_id),
        "user2_id": str(user2_id),
        "session1_id": str(session1_id),
        "session2_id": str(session2_id),
    }


class TestRLSUsers:
    """RLS tests for users table."""

    def test_rls_users_cross_tenant_read_blocked(self, tenant_data):
        """Tenant A cannot SELECT tenant B users."""
        conn = get_app_connection()
        cur = conn.cursor()

        # Set context to tenant1, try to read tenant2's user - should see only tenant1's user (1 row)
        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (tenant_data["tenant1_id"],))
        cur.execute("SELECT * FROM users WHERE tenant_id IS NOT NULL")
        rows = cur.fetchall()
        assert len(rows) == 1, f"RLS failed: tenant1 should see own user, got {len(rows)}"
        assert rows[0][2] == "user1@tenant1.com"

        # Set context to tenant2, try to read tenant1's user - should see only tenant2's user (1 row)
        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (tenant_data["tenant2_id"],))
        cur.execute("SELECT * FROM users WHERE tenant_id IS NOT NULL")
        rows = cur.fetchall()
        assert len(rows) == 1, f"RLS failed: tenant2 should see own user, got {len(rows)}"
        assert rows[0][2] == "user2@tenant2.com"

        # Verify tenant1 cannot see tenant2's user by checking email
        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (tenant_data["tenant1_id"],))
        cur.execute("SELECT email FROM users WHERE tenant_id IS NOT NULL")
        rows = cur.fetchall()
        emails = [r[0] for r in rows]
        assert "user2@tenant2.com" not in emails, "Tenant1 can see tenant2's user!"

        cur.close()
        conn.close()

    def test_rls_users_cross_tenant_read_allowed(self, tenant_data):
        """Tenant A CAN SELECT own users."""
        conn = get_app_connection()
        cur = conn.cursor()

        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (tenant_data["tenant1_id"],))
        cur.execute("SELECT * FROM users WHERE tenant_id IS NOT NULL")
        rows = cur.fetchall()
        assert len(rows) == 1, f"RLS failed: expected 1 row, got {len(rows)}"
        assert rows[0][2] == "user1@tenant1.com"

        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (tenant_data["tenant2_id"],))
        cur.execute("SELECT * FROM users WHERE tenant_id IS NOT NULL")
        rows = cur.fetchall()
        assert len(rows) == 1, f"RLS failed: expected 1 row, got {len(rows)}"
        assert rows[0][2] == "user2@tenant2.com"

        cur.close()
        conn.close()

    def test_rls_users_cross_tenant_update_blocked(self, tenant_data):
        """Tenant A cannot UPDATE tenant B users."""
        conn = get_app_connection()
        cur = conn.cursor()

        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (tenant_data["tenant2_id"],))
        cur.execute(
            "UPDATE users SET email = 'hacked@tenant2.com' WHERE id = %s",
            (tenant_data["user1_id"],)
        )
        assert cur.rowcount == 0, f"RLS failed: UPDATE affected {cur.rowcount} rows"

        conn.commit()
        cur.close()
        conn.close()

    def test_rls_users_cross_tenant_delete_blocked(self, tenant_data):
        """Tenant A cannot DELETE tenant B users."""
        conn = get_app_connection()
        cur = conn.cursor()

        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (tenant_data["tenant2_id"],))
        cur.execute("DELETE FROM users WHERE id = %s", (tenant_data["user1_id"],))
        assert cur.rowcount == 0, f"RLS failed: DELETE affected {cur.rowcount} rows"

        conn.commit()
        cur.close()
        conn.close()


class TestRLSSessions:
    """RLS tests for sessions table."""

    def test_rls_sessions_cross_tenant_read_blocked(self, tenant_data):
        """Tenant A cannot SELECT tenant B sessions."""
        conn = get_app_connection()
        cur = conn.cursor()

        # Set context to tenant1, try to read tenant2's session - should see only tenant1's session
        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (tenant_data["tenant1_id"],))
        cur.execute("SELECT * FROM sessions")
        rows = cur.fetchall()
        assert len(rows) == 1, f"RLS failed: tenant1 should see own session, got {len(rows)}"
        assert rows[0][2] == tenant_data["tenant1_id"]

        # Set context to tenant2, try to read tenant1's session - should see only tenant2's session
        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (tenant_data["tenant2_id"],))
        cur.execute("SELECT * FROM sessions")
        rows = cur.fetchall()
        assert len(rows) == 1, f"RLS failed: tenant2 should see own session, got {len(rows)}"
        assert rows[0][2] == tenant_data["tenant2_id"]

        # Verify tenant1 cannot see tenant2's session by checking tenant_id
        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (tenant_data["tenant1_id"],))
        cur.execute("SELECT tenant_id FROM sessions")
        rows = cur.fetchall()
        tenant_ids = [str(r[0]) for r in rows]
        assert tenant_data["tenant2_id"] not in tenant_ids, "Tenant1 can see tenant2's session!"

        cur.close()
        conn.close()

    def test_rls_sessions_cross_tenant_read_allowed(self, tenant_data):
        """Tenant A CAN SELECT own sessions."""
        conn = get_app_connection()
        cur = conn.cursor()

        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (tenant_data["tenant1_id"],))
        cur.execute("SELECT * FROM sessions")
        rows = cur.fetchall()
        assert len(rows) == 1, f"RLS failed: expected 1 row, got {len(rows)}"
        assert rows[0][1] == tenant_data["user1_id"]

        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (tenant_data["tenant2_id"],))
        cur.execute("SELECT * FROM sessions")
        rows = cur.fetchall()
        assert len(rows) == 1, f"RLS failed: expected 1 row, got {len(rows)}"
        assert rows[0][1] == tenant_data["user2_id"]

        cur.close()
        conn.close()

    def test_rls_sessions_cross_tenant_update_blocked(self, tenant_data):
        """Tenant A cannot UPDATE tenant B sessions (e.g., revoke)."""
        conn = get_app_connection()
        cur = conn.cursor()

        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (tenant_data["tenant2_id"],))
        cur.execute(
            "UPDATE sessions SET is_revoked = TRUE WHERE id = %s",
            (tenant_data["session1_id"],)
        )
        assert cur.rowcount == 0, f"RLS failed: UPDATE affected {cur.rowcount} rows"

        conn.commit()
        cur.close()
        conn.close()

    def test_rls_sessions_cross_tenant_delete_blocked(self, tenant_data):
        """Tenant A cannot DELETE tenant B sessions."""
        conn = get_app_connection()
        cur = conn.cursor()

        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (tenant_data["tenant2_id"],))
        cur.execute("DELETE FROM sessions WHERE id = %s", (tenant_data["session1_id"],))
        assert cur.rowcount == 0, f"RLS failed: DELETE affected {cur.rowcount} rows"

        conn.commit()
        cur.close()
        conn.close()


class TestRLSNoContext:
    """Tests for sessions with no tenant context set."""

    def test_no_tenant_context_returns_zero_users(self, tenant_data):
        """Session with no app.current_tenant returns 0 rows from users."""
        conn = get_app_connection()
        cur = conn.cursor()

        # Don't set any tenant context
        cur.execute("SELECT * FROM users WHERE tenant_id IS NOT NULL")
        rows = cur.fetchall()
        assert len(rows) == 0, f"Expected 0 rows without tenant context, got {len(rows)}"

        cur.close()
        conn.close()

    def test_no_tenant_context_returns_zero_sessions(self, tenant_data):
        """Session with no app.current_tenant returns 0 rows from sessions."""
        conn = get_app_connection()
        cur = conn.cursor()

        cur.execute("SELECT * FROM sessions")
        rows = cur.fetchall()
        assert len(rows) == 0, f"Expected 0 rows without tenant context, got {len(rows)}"

        cur.close()
        conn.close()


class TestRLSRoles:
    """Tests for database role permissions."""

    def test_app_role_cannot_bypass_rls(self, tenant_data):
        """vaultiq_app role is blocked by RLS (no BYPASSRLS) - can only see data for current tenant."""
        conn = get_app_connection()
        cur = conn.cursor()

        # Set tenant context to tenant2 - should see only tenant2's data
        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (tenant_data["tenant2_id"],))
        cur.execute("SELECT * FROM users WHERE tenant_id IS NOT NULL")
        rows = cur.fetchall()
        assert len(rows) == 1, f"RLS failed: should see tenant2's data, got {len(rows)}"
        assert rows[0][2] == "user2@tenant2.com"

        # Set tenant context to tenant1 - should see only tenant1's data
        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (tenant_data["tenant1_id"],))
        cur.execute("SELECT * FROM users WHERE tenant_id IS NOT NULL")
        rows = cur.fetchall()
        assert len(rows) == 1, f"RLS failed: should see tenant1's data, got {len(rows)}"
        assert rows[0][2] == "user1@tenant1.com"

        # Verify tenant1 cannot see tenant2's user
        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (tenant_data["tenant1_id"],))
        cur.execute("SELECT email FROM users WHERE tenant_id IS NOT NULL")
        rows = cur.fetchall()
        emails = [r[0] for r in rows]
        assert "user2@tenant2.com" not in emails, "vaultiq_app bypassed RLS: tenant1 can see tenant2's user!"

        cur.close()
        conn.close()

    def test_super_admin_role_limited_grants(self, tenant_data):
        """vaultiq_super_admin can only read tenants table, not users/sessions."""
        conn = get_super_admin_connection()
        cur = conn.cursor()

        # Should be able to read tenants
        cur.execute("SELECT * FROM tenants")
        rows = cur.fetchall()
        assert len(rows) == 2, f"Super admin should read tenants: got {len(rows)}"

        # Should NOT be able to read users (no grant) - expect permission denied
        try:
            cur.execute("SELECT * FROM users")
            assert False, "Super admin should not have permission to read users"
        except psycopg2.errors.InsufficientPrivilege:
            conn.rollback()  # Reset transaction
            pass  # Expected

        # Should NOT be able to read sessions (no grant) - expect permission denied
        try:
            cur.execute("SELECT * FROM sessions")
            assert False, "Super admin should not have permission to read sessions"
        except psycopg2.errors.InsufficientPrivilege:
            conn.rollback()  # Reset transaction
            pass  # Expected

        cur.close()
        conn.close()

    def test_super_admin_no_bypassrls(self, tenant_data):
        """vaultiq_super_admin has NOBYPASSRLS and no grants on tenant data."""
        conn = get_super_admin_connection()
        cur = conn.cursor()

        # Even with tenant context set, super_admin has no grants on users
        cur.execute("SELECT set_config('app.current_tenant', %s, true)", (tenant_data["tenant1_id"],))
        try:
            cur.execute("SELECT * FROM users")
            assert False, "Super admin should not have permission to read users"
        except psycopg2.errors.InsufficientPrivilege:
            pass  # Expected - no grant, so permission denied

        cur.close()
        conn.close()


class TestRLSAsync:
    """Async tests using SQLAlchemy session."""

    @pytest.mark.asyncio
    async def test_set_tenant_context_helper(self, app_db_session: AsyncSession):
        """Test set_tenant_context helper works."""
        from app.database import set_tenant_context

        tenant_id = str(uuid.uuid4())
        await set_tenant_context(app_db_session, tenant_id)

        result = await app_db_session.execute(text("SHOW app.current_tenant"))
        current = result.scalar()
        assert current == tenant_id

    @pytest.mark.asyncio
    async def test_cross_tenant_isolation_via_orm(self, app_db_session: AsyncSession):
        """Test cross-tenant isolation using ORM with tenant context."""
        from app.database import set_tenant_context

        # Create two tenants
        tenant1 = Tenant(short_code="TEST1", name="Test Tenant 1")
        tenant2 = Tenant(short_code="TEST2", name="Test Tenant 2")
        app_db_session.add_all([tenant1, tenant2])
        await app_db_session.commit()
        await app_db_session.refresh(tenant1)
        await app_db_session.refresh(tenant2)

        # Create user for tenant1
        user1 = User(tenant_id=tenant1.id, email="user@test1.com", password_hash="hash", role="employee")
        app_db_session.add(user1)
        await app_db_session.commit()

        # Set context to tenant2 - should not see tenant1's user
        await set_tenant_context(app_db_session, str(tenant2.id))
        result = await app_db_session.execute(text("SELECT * FROM users WHERE tenant_id IS NOT NULL"))
        rows = result.fetchall()
        assert len(rows) == 0

        # Set context to tenant1 - should see user
        await set_tenant_context(app_db_session, str(tenant1.id))
        result = await app_db_session.execute(text("SELECT * FROM users WHERE tenant_id IS NOT NULL"))
        rows = result.fetchall()
        assert len(rows) == 1