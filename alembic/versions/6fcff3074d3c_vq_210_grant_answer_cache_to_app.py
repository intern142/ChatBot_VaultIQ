"""VQ-210: Grant answer_cache permissions to vaultiq_app

Revision ID: 6fcff3074d3c
Revises: 49371df05e77
Create Date: 2026-10-01 21:41:10.100179

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6fcff3074d3c'
down_revision: Union[str, None] = '49371df05e77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # vaultiq_app needs SELECT, INSERT, UPDATE, DELETE on answer_cache for RLS enforcement
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON answer_cache TO vaultiq_app")


def downgrade() -> None:
    op.execute("REVOKE SELECT, INSERT, UPDATE, DELETE ON answer_cache FROM vaultiq_app")
