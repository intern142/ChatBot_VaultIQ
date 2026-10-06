"""VQ-210: Add knowledge_base_version to tenants

Revision ID: 49371df05e77
Revises: 33449491a285
Create Date: 2026-10-01 20:42:50.970841

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '49371df05e77'
down_revision: Union[str, None] = '33449491a285'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("knowledge_base_version", sa.Integer, nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("tenants", "knowledge_base_version")
