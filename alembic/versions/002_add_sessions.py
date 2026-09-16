"""VQ-105: Add sessions table and lockout columns to users

Revision ID: 002_add_sessions
Revises: 001_initial
Create Date: 2026-09-15

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_add_sessions"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash VARCHAR(255) NOT NULL,
            is_revoked BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ NOT NULL,
            revoked_at TIMESTAMPTZ
        )
    """)

    op.execute("CREATE INDEX idx_sessions_user_id ON sessions(user_id)")
    op.execute("CREATE INDEX idx_sessions_token_hash ON sessions(token_hash)")

    op.execute("ALTER TABLE users ADD COLUMN failed_login_attempts INTEGER DEFAULT 0")
    op.execute("ALTER TABLE users ADD COLUMN locked_until TIMESTAMPTZ")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN locked_until")
    op.execute("ALTER TABLE users DROP COLUMN failed_login_attempts")
    op.drop_table("sessions")
