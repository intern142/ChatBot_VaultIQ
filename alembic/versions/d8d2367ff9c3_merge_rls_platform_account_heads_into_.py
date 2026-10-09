"""Merge RLS platform-account heads into BE_accurate

Revision ID: d8d2367ff9c3
Revises: 007_rls_platform_accounts, 008_rls_platform_accounts, 497ef5bc8a61
Create Date: 2026-10-09 16:44:53.071146

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8d2367ff9c3'
down_revision: Union[str, None] = ('007_rls_platform_accounts', '008_rls_platform_accounts', '497ef5bc8a61')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
