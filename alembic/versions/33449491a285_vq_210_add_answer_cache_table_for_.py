"""VQ-210: Add answer_cache table for tenant-scoped answer caching

Revision ID: 33449491a285
Revises: 006_sessions_tenant_nullable
Create Date: 2026-10-01 20:23:48.150980

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '33449491a285'
down_revision: Union[str, None] = '006_sessions_tenant_nullable'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "answer_cache",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("question_hash", sa.CHAR(64), nullable=False),
        sa.Column("kb_version", sa.Integer, nullable=False),
        sa.Column("answer_text", sa.Text, nullable=False),
        sa.Column("source_document_id", sa.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_chunk_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("tenant_id", "role", "question_hash", "kb_version", name="uq_answer_cache_tenant_role_qhash_kb"),
    )

    # Indexes
    op.create_index("ix_answer_cache_lookup", "answer_cache", ["tenant_id", "role", "question_hash", "kb_version"])
    op.create_index("ix_answer_cache_invalidate", "answer_cache", ["tenant_id", "kb_version"])

    # RLS
    op.execute("ALTER TABLE answer_cache ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE answer_cache FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON answer_cache "
        "USING (tenant_id = current_setting('app.current_tenant', true)::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON answer_cache")
    op.execute("ALTER TABLE answer_cache DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_answer_cache_invalidate", table_name="answer_cache")
    op.drop_index("ix_answer_cache_lookup", table_name="answer_cache")
    op.drop_table("answer_cache")
