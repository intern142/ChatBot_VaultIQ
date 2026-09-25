"""Make sessions.tenant_id nullable for super-admin sessions

Sessions for platform (Super Admin) users are intentionally not linked to
a tenant (VQ-101 AC3: super admin accounts are the only accounts not tied
to a tenant). The Session model declares tenant_id nullable, and both the
login route and test fixtures insert NULL for super-admin sessions.
Migration 002 wrongly created the column NOT NULL, which breaks a freshly
migrated database (CI) while leaving older databases nullable. This
migration aligns the schema with the model.

Revision ID: 006_sessions_tenant_nullable
Revises: 005_invite_code_lookup
Create Date: 2026-09-24

"""
from typing import Sequence, Union
from alembic import op

revision: str = "006_sessions_tenant_nullable"
down_revision: Union[str, None] = "005_invite_code_lookup"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE sessions ALTER COLUMN tenant_id DROP NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE sessions ALTER COLUMN tenant_id SET NOT NULL")