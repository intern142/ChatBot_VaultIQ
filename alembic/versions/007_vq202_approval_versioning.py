"""VQ-202: approval workflow and document versions

Adds the approval state machine to `documents`, groups versions of the same logical
document, and gives each tenant a knowledge base version that moves whenever the
approved set changes.

The invariant that matters: at most one approved version per logical document. That is
enforced structurally by a partial unique index rather than only in application code, so
a bug in a route handler cannot leave two versions answering at once.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "007_vq202_approval_versioning"
down_revision: Union[str, None] = "006_sessions_tenant_nullable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

STATUS_VALUES = ("pending", "approved", "archived", "rejected")


def upgrade() -> None:
    op.execute("CREATE TYPE document_approval_status AS ENUM (%s)" % ", ".join(
        f"'{v}'" for v in STATUS_VALUES
    ))

    # Existing rows each become a logical document of their own, version 1, pending.
    # Nothing is auto-approved: VQ-202 exists precisely so that a human decides what is
    # searchable, and silently promoting existing content would do the opposite.
    op.add_column(
        "documents",
        sa.Column("status", sa.Enum(*STATUS_VALUES, name="document_approval_status"),
                  nullable=False, server_default="pending"),
    )
    op.add_column(
        "documents",
        sa.Column("document_group_id", sa.dialects.postgresql.UUID(as_uuid=True),
                  nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "documents",
        sa.Column("supersedes_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("approved_by", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("decision_note", sa.Text(), nullable=True),
    )

    op.create_foreign_key(
        "fk_documents_approved_by", "documents", "users",
        ["approved_by"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_documents_supersedes", "documents", "documents",
        ["supersedes_id"], ["id"], ondelete="SET NULL",
    )

    # Backfill the group id now that the column exists.
    op.execute("UPDATE documents SET document_group_id = id WHERE document_group_id IS NULL")
    op.execute("ALTER TABLE documents ALTER COLUMN document_group_id SET NOT NULL")

    # A logical document never spans tenants, so this index cannot be used to probe
    # another tenant's groups.
    op.execute("CREATE UNIQUE INDEX uq_documents_group_version "
               "ON documents (document_group_id, version_number)")
    op.execute("CREATE INDEX ix_documents_group ON documents (document_group_id, version_number)")
    op.execute("CREATE INDEX ix_documents_tenant_status ON documents (tenant_id, status)")

    # The invariant. At most one approved version per logical document, enforced by
    # Postgres. Retiring the old version before promoting the new one keeps this
    # satisfied at every statement inside the approval transaction.
    op.execute("CREATE UNIQUE INDEX uq_documents_one_approved_per_group "
               "ON documents (document_group_id) WHERE status = 'approved'")

    # Idempotent: 49371df05e77 (VQ-210) may have already added this column
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('tenants')]
    if 'knowledge_base_version' not in columns:
        op.add_column(
            "tenants",
            sa.Column("knowledge_base_version", sa.Integer(), nullable=False, server_default="1"),
        )

    # The documents policy was created by the VQ-104 migration as
    #   current_setting('app.current_tenant'::text)      <- no missing_ok
    # Every other tenant table passes true as the second argument. Without it
    # Postgres raises `unrecognized configuration parameter "app.current_tenant"`
    # instead of returning NULL, so any query on documents in a transaction that
    # never set the context is a 500 rather than an empty result. That is reachable
    # in normal operation: SET LOCAL is transaction-scoped, so a refresh after
    # commit runs in a fresh transaction with the setting gone.
    #
    # With missing_ok the expression yields NULL, the comparison is never true, and
    # the query returns zero rows. That is the behaviour VQ-102 AC3 asks for - a
    # no-tenant session sees nothing - and it fails closed rather than erroring.
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON documents")
    op.execute(
        "CREATE POLICY tenant_isolation ON documents "
        "USING (tenant_id = current_setting('app.current_tenant', true)::uuid)"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON documents")
    op.execute(
        "CREATE POLICY tenant_isolation ON documents "
        "USING (tenant_id = current_setting('app.current_tenant'::text)::uuid)"
    )

    op.drop_column("tenants", "knowledge_base_version")

    op.execute("DROP INDEX IF EXISTS uq_documents_one_approved_per_group")
    op.execute("DROP INDEX IF EXISTS ix_documents_tenant_status")
    op.execute("DROP INDEX IF EXISTS ix_documents_group")
    op.execute("DROP INDEX IF EXISTS uq_documents_group_version")

    op.drop_constraint("fk_documents_supersedes", "documents", type_="foreignkey")
    op.drop_constraint("fk_documents_approved_by", "documents", type_="foreignkey")

    for col in ("decision_note", "approved_at", "approved_by", "supersedes_id",
                "version_number", "document_group_id", "status"):
        op.drop_column("documents", col)

    op.execute("DROP TYPE IF EXISTS document_approval_status")
