"""VQ-107: Tenant lifecycle — invites, audit_logs, storage_quota_mb

Revision ID: 004_tenant_lifecycle
Revises: 003_rls_hardening
Create Date: 2026-09-21

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "004_tenant_lifecycle"
down_revision: Union[str, None] = "a1340d9f596a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Add storage_quota_mb to tenants ---
    op.execute("ALTER TABLE tenants ADD COLUMN storage_quota_mb INTEGER")

    # --- Create invites table ---
    op.execute("""
        CREATE TABLE invites (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            email VARCHAR(255) NOT NULL,
            code VARCHAR(64) UNIQUE NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            used_at TIMESTAMPTZ,
            created_by UUID NOT NULL REFERENCES users(id),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX idx_invites_tenant_id ON invites(tenant_id)")
    op.execute("CREATE INDEX idx_invites_code ON invites(code)")

    # --- Create audit_logs table ---
    op.execute("""
        CREATE TABLE audit_logs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            actor_user_id UUID REFERENCES users(id),
            actor_role user_role NOT NULL,
            action VARCHAR(100) NOT NULL,
            target_type VARCHAR(50) NOT NULL,
            target_id UUID NOT NULL,
            details JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX idx_audit_logs_tenant_id ON audit_logs(tenant_id)")
    op.execute("CREATE INDEX idx_audit_logs_actor_user_id ON audit_logs(actor_user_id)")
    op.execute("CREATE INDEX idx_audit_logs_target ON audit_logs(target_type, target_id)")

    # --- RLS on invites ---
    op.execute("ALTER TABLE invites ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE invites FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON invites
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)

    # --- RLS on audit_logs ---
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON audit_logs
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)

    # --- Grants for vaultiq_app ---
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON invites TO vaultiq_app")
    op.execute("GRANT SELECT, INSERT ON audit_logs TO vaultiq_app")

    # vaultiq_super_admin: NO grants on invites, audit_logs (admin API uses vaultiq_app connection)


def downgrade() -> None:
    # Drop grants
    op.execute("REVOKE ALL ON invites FROM vaultiq_app")
    op.execute("REVOKE ALL ON audit_logs FROM vaultiq_app")

    # Drop RLS
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON audit_logs")
    op.execute("ALTER TABLE audit_logs DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON invites")
    op.execute("ALTER TABLE invites DISABLE ROW LEVEL SECURITY")

    # Drop tables
    op.drop_table("audit_logs")
    op.drop_table("invites")

    # Drop column
    op.execute("ALTER TABLE tenants DROP COLUMN storage_quota_mb")