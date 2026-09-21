"""VQ-103: Add is_active and manager_id to users

Revision ID: 002_add_is_active_and_manager
Revises: 001_initial
Create Date: 2026-09-21

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_add_is_active_and_manager"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("users", sa.Column("manager_id", sa.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_users_manager_id", "users", "users", ["manager_id"], ["id"], ondelete="SET NULL")
    op.create_index("idx_users_manager_id", "users", ["manager_id"])
    op.execute("ALTER TABLE users ALTER COLUMN is_active DROP DEFAULT")


def downgrade() -> None:
    op.drop_index("idx_users_manager_id", table_name="users")
    op.drop_constraint("fk_users_manager_id", "users", type_="foreignkey")
    op.drop_column("users", "manager_id")
    op.drop_column("users", "is_active")