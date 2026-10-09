"""Fix Known Defect #2: RLS policies for platform (super_admin) accounts

Revision ID: 007_rls_platform_accounts
Revises: 006_sessions_tenant_nullable
Create Date: 2026-10-08
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "007_rls_platform_accounts"
down_revision: Union[str, None] = "006_sessions_tenant_nullable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SUPER_ADMIN_TENANT_ID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    # --- users table: allow super_admin dummy UUID to match NULL tenant_id ---
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON users")
    op.execute(f"""
        CREATE POLICY tenant_isolation ON users
        USING (
            tenant_id = current_setting('app.current_tenant', true)::uuid
            OR (
                tenant_id IS NULL
                AND current_setting('app.current_tenant', true) = '{SUPER_ADMIN_TENANT_ID}'
            )
        )
    """)

    # --- sessions table: allow super_admin dummy UUID to match NULL tenant_id ---
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON sessions")
    op.execute(f"""
        CREATE POLICY tenant_isolation ON sessions
        USING (
            tenant_id = current_setting('app.current_tenant', true)::uuid
            OR (
                tenant_id IS NULL
                AND current_setting('app.current_tenant', true) = '{SUPER_ADMIN_TENANT_ID}'
            )
        )
    """)


def downgrade() -> None:
    # Restore original policies (tenant_id = current_setting only)
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON users")
    op.execute("""
        CREATE POLICY tenant_isolation ON users
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON sessions")
    op.execute("""
        CREATE POLICY tenant_isolation ON sessions
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)