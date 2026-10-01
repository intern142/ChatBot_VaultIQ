"""merge heads for quota default

Revision ID: 6dea5135f692
Revises: 006_sessions_tenant_nullable, 16d34f2baf40
Create Date: 2026-10-01 15:54:12.570626

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6dea5135f692'
down_revision: Union[str, None] = ('006_sessions_tenant_nullable', '16d34f2baf40')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
