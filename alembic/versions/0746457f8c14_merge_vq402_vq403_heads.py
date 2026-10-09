"""merge_vq402_vq403_heads

Revision ID: 0746457f8c14
Revises: 007_audit_retention, 007_offboarding
Create Date: 2026-10-09 14:51:50.895078

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0746457f8c14'
down_revision: Union[str, None] = ('007_audit_retention', '007_offboarding')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
