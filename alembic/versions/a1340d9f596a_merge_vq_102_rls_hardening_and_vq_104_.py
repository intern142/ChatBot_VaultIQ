"""Merge VQ-102 RLS hardening and VQ-104 documents

Revision ID: a1340d9f596a
Revises: 003_rls_hardening, d9ecec7d2e04
Create Date: 2026-09-21 21:20:53.258601

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1340d9f596a'
down_revision: Union[str, None] = ('003_rls_hardening', 'd9ecec7d2e04')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
