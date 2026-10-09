"""Add delegated-permission flags to tenants for Feature 2

Super Admin can grant a Client Admin the ability to (a) add users to their own
tenant and/or (b) create new tenants. The grants live as booleans on the tenant
row:

  - can_add_users:      the tenant's Client Admin may directly create user
                        accounts (employees / a second client admin) in the
                        tenant.
  - can_create_tenants: the tenant's Client Admin may create new tenants and
                        set up their first Client Admin.

created_by_user_id records which user created the tenant through the delegated
client-admin flow, so the creator is the only tenant user who may set up its
first admin (prevents a Client Admin from touching another org's tenant).

Revision ID: 007_tenant_permissions
Revises: 006_sessions_tenant_nullable
Create Date: 2026-10-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "007_tenant_permissions"
down_revision: Union[str, None] = "006_sessions_tenant_nullable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("can_add_users", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "tenants",
        sa.Column("can_create_tenants", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column("tenants", sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_tenants_created_by_user_id",
        "tenants",
        "users",
        ["created_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_tenants_created_by_user_id", "tenants", type_="foreignkey")
    op.drop_column("tenants", "created_by_user_id")
    op.drop_column("tenants", "can_create_tenants")
    op.drop_column("tenants", "can_add_users")