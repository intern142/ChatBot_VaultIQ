"""set default storage_quota_mb to 20

Revision ID: f8715172a15a
Revises: 6dea5135f692
Create Date: 2026-10-01 15:54:30.075258

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8715172a15a'
down_revision: Union[str, None] = '6dea5135f692'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update existing NULL quotas to 20
    op.execute("UPDATE tenants SET storage_quota_mb = 20 WHERE storage_quota_mb IS NULL")
    # Set column default to 20
    op.alter_column("tenants", "storage_quota_mb", server_default=sa.text("20"))


def downgrade() -> None:
    op.alter_column("tenants", "storage_quota_mb", server_default=None)
