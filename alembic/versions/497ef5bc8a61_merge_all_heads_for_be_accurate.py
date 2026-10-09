"""merge_all_heads_for_be_accurate

Revision ID: 497ef5bc8a61
Revises: 012_merge_sprint3_heads, 011_super_admin_grants, 0746457f8c14, 160ccbed24a5, 5cf4dcd6b1b1, 6fcff3074d3c
Create Date: 2026-10-09 14:56:03.488401

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '497ef5bc8a61'
down_revision: Union[str, None] = ('012_merge_sprint3_heads', '011_super_admin_grants', '0746457f8c14', '160ccbed24a5', '5cf4dcd6b1b1', '6fcff3074d3c')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
