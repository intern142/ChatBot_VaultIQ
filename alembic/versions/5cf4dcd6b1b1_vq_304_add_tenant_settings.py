"""VQ-304: Add tenant_settings table for tenant configuration

Revision ID: 5cf4dcd6b1b1
Revises: 006_sessions_tenant_nullable
Create Date: 2026-10-01 22:35:13.058798

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '5cf4dcd6b1b1'
down_revision: Union[str, None] = '006_sessions_tenant_nullable'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_settings",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                  primary_key=True, nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("logo_path", sa.String(500), nullable=True),
        sa.Column("accent_colour", sa.String(7), nullable=True),  # #RRGGBB or #RGB
        sa.Column("not_found_message", sa.Text(), nullable=True),
        sa.Column("allowed_upload_formats", postgresql.JSONB(), nullable=True),
        sa.Column("conversation_retention_days", sa.Integer(), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )

    # Enable RLS
    op.execute("ALTER TABLE tenant_settings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_settings FORCE ROW LEVEL SECURITY")

    # RLS Policy
    op.execute("""
        CREATE POLICY tenant_isolation ON tenant_settings
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)

    # Grants for vaultiq_app
    op.execute("GRANT SELECT, INSERT, UPDATE ON tenant_settings TO vaultiq_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON tenant_settings")
    op.execute("ALTER TABLE tenant_settings DISABLE ROW LEVEL SECURITY")
    op.execute("REVOKE SELECT, INSERT, UPDATE ON tenant_settings FROM vaultiq_app")
    op.drop_table("tenant_settings")