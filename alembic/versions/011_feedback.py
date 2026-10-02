"""Answer feedback capture (VQ-305)

Revision ID: 011_feedback
Revises: 010_search_index
Create Date: 2026-10-02

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "011_feedback"
down_revision: Union[str, None] = "006_sessions_tenant_nullable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Answers table
    op.execute("""
        CREATE TABLE answers (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            question text NOT NULL,
            answer_text text,
            confidence float,
            source_document_ids uuid[] NOT NULL DEFAULT '{}',
            source_chunk_ids uuid[] NOT NULL DEFAULT '{}',
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ON answers (tenant_id, user_id, created_at)")
    op.execute("CREATE INDEX ON answers (tenant_id, created_at)")

    # Answer feedback table
    op.execute("""
        CREATE TABLE answer_feedback (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            answer_id uuid NOT NULL REFERENCES answers(id) ON DELETE CASCADE,
            vote smallint NOT NULL CHECK (vote IN (1, -1)),
            comment text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (answer_id, user_id)
        )
    """)
    op.execute("CREATE INDEX ON answer_feedback (tenant_id, user_id)")
    op.execute("CREATE INDEX ON answer_feedback (tenant_id, answer_id)")

    # RLS on answers
    op.execute("ALTER TABLE answers ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE answers FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY answers_tenant_isolation ON answers
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)

    # RLS on answer_feedback
    op.execute("ALTER TABLE answer_feedback ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE answer_feedback FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY answer_feedback_tenant_isolation ON answer_feedback
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)

    # Grants for vaultiq_app
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON answers TO vaultiq_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON answer_feedback TO vaultiq_app")

    # Grants for vaultiq_super_admin (read-only for platform analytics)
    op.execute("GRANT SELECT ON answers TO vaultiq_super_admin")
    op.execute("GRANT SELECT ON answer_feedback TO vaultiq_super_admin")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS answer_feedback")
    op.execute("DROP TABLE IF EXISTS answers")