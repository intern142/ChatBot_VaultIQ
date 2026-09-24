"""VQ-102: RLS hardening — FORCE RLS on all tenant tables + dedicated roles

Revision ID: 003_rls_hardening
Revises: 001_initial
Create Date: 2026-09-18

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003_rls_hardening"
down_revision: Union[str, None] = "002_add_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- FORCE RLS on users table (already has policy) ---
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON users")
    op.execute("""
        CREATE POLICY tenant_isolation ON users
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)

    # --- RLS + FORCE RLS on sessions table ---
    op.execute("ALTER TABLE sessions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE sessions FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON sessions
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)

    # Note: documents table will be handled when vq-104 is merged
    # For now, we add the FORCE RLS here assuming documents exists
    # This will be idempotent if documents doesn't exist yet
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'documents') THEN ALTER TABLE documents FORCE ROW LEVEL SECURITY; END IF; END $$")

    # --- Create dedicated database roles ---
    # vaultiq_app: application runtime, NO BYPASSRLS
    op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vaultiq_app') THEN CREATE ROLE vaultiq_app NOINHERIT LOGIN PASSWORD 'vaultiq_secret'; END IF; END $$")
    op.execute("ALTER ROLE vaultiq_app SET search_path = public")
    op.execute("GRANT USAGE ON SCHEMA public TO vaultiq_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON users, sessions TO vaultiq_app")
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'documents') THEN GRANT SELECT, INSERT, UPDATE, DELETE ON documents TO vaultiq_app; END IF; END $$")

    # vaultiq_super_admin: platform operator reads, NO BYPASSRLS, limited grants
    op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vaultiq_super_admin') THEN CREATE ROLE vaultiq_super_admin NOINHERIT LOGIN PASSWORD 'vaultiq_secret'; END IF; END $$")
    op.execute("ALTER ROLE vaultiq_super_admin SET search_path = public")
    op.execute("GRANT USAGE ON SCHEMA public TO vaultiq_super_admin")
    op.execute("GRANT SELECT ON tenants TO vaultiq_super_admin")
    # Explicitly NO grants on users, sessions, documents, etc.

    # Ensure RLS applies to these roles (no BYPASSRLS)
    op.execute("ALTER ROLE vaultiq_app NOBYPASSRLS")
    op.execute("ALTER ROLE vaultiq_super_admin NOBYPASSRLS")


def downgrade() -> None:
    # Drop roles
    op.execute("DROP ROLE IF EXISTS vaultiq_super_admin")
    op.execute("DROP ROLE IF EXISTS vaultiq_app")

    # Drop FORCE RLS (disable RLS entirely for clean rollback)
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'documents') THEN ALTER TABLE documents DISABLE ROW LEVEL SECURITY; END IF; END $$")
    op.execute("ALTER TABLE sessions DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")