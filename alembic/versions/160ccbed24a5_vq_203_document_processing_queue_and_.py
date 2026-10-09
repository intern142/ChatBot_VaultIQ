"""VQ-203: document processing queue and status

Adds per-document processing status fields and a tenant-scoped job queue table
for background document processing (text extraction, chunking, embedding, indexing).

Processing status enum: queued, processing, ready, failed
Job status enum: queued, processing, done, failed

Both tables inherit tenant isolation via existing RLS policies.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM

# SQLAlchemy 2.0.23 predates the pgvector dialect type, so the column is
# declared as a plain custom type. The extension is created in upgrade() below.
from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType):
    """pgvector column of fixed dimension."""

    cache_ok = True

    def __init__(self, dim: int):
        super().__init__()
        self.dim = dim

    def get_col_spec(self, **kw):
        return f"vector({self.dim})"

# revision identifiers, used by Alembic.
#
# down_revision is 006_sessions_tenant_nullable, the head of the chain this
# branch is built on. It was originally a1340d9f596a, but that revision is the
# merge point of 003/d9ecec7d2e04 and 004_tenant_lifecycle already forks from
# it, so pointing here too produced two heads and `alembic upgrade head` failed
# with "Multiple head revisions are present".
revision: str = '160ccbed24a5'
down_revision: Union[str, None] = '006_sessions_tenant_nullable'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PROCESSING_STATUS_ENUM = ENUM(
    'queued', 'processing', 'ready', 'failed',
    name='processing_status',
    create_type=False
)

JOB_STATUS_ENUM = ENUM(
    'queued', 'processing', 'done', 'failed',
    name='job_status',
    create_type=False
)


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE processing_status AS ENUM ('queued', 'processing', 'ready', 'failed')")
    op.execute("CREATE TYPE job_status AS ENUM ('queued', 'processing', 'done', 'failed')")

    # Add processing fields to documents
    op.add_column(
        'documents',
        sa.Column(
            'processing_status',
            PROCESSING_STATUS_ENUM,
            nullable=False,
            server_default='queued',
        )
    )
    op.add_column(
        'documents',
        sa.Column('processing_error', sa.Text, nullable=True)
    )
    op.add_column(
        'documents',
        sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'documents',
        sa.Column('processing_completed_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'documents',
        sa.Column('processing_version', sa.Integer, nullable=False, server_default='1')
    )

    # Create document_jobs table
    op.create_table(
        'document_jobs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('document_id', UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', JOB_STATUS_ENUM, nullable=False, server_default='queued'),
        sa.Column('retry_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer, nullable=False, server_default='3'),
        sa.Column('last_error', sa.Text, nullable=True),
        sa.Column('payload', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )

    # Index for fair dequeue: tenant + status + created_at
    op.create_index(
        'ix_document_jobs_tenant_status_created',
        'document_jobs',
        ['tenant_id', 'status', 'created_at'],
    )

    # Idempotency: unique constraint on (document_id, payload) — payload includes version
    op.create_unique_constraint(
        'uq_document_jobs_document_payload',
        'document_jobs',
        ['document_id', 'payload'],
    )

    # RLS on document_jobs
    op.execute("ALTER TABLE document_jobs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE document_jobs FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON document_jobs
        FOR ALL TO vaultiq_app
        USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON document_jobs TO vaultiq_app")

    # Chunk + embedding store. Created here rather than lazily from the worker:
    # vaultiq_app has no CREATE on schema public, so DDL from the application
    # fails outright, and schema changes belong in a revision regardless.
    # Idempotent: 010_search_index (VQ-204) may have already created this table
    # (partitioned). If it exists, skip creation but ensure grants/policies match.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if not inspector.has_table('document_chunks'):
        op.create_table(
            'document_chunks',
            sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
            sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
            sa.Column('document_id', UUID(as_uuid=True), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False),
            sa.Column('chunk_index', sa.Integer, nullable=False),
            sa.Column('content', sa.Text, nullable=False),
            sa.Column('embedding', Vector(384), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
            sa.UniqueConstraint('document_id', 'chunk_index', name='uq_document_chunks_document_index'),
        )
        op.create_index(
            'ix_document_chunks_tenant_document',
            'document_chunks',
            ['tenant_id', 'document_id'],
        )
    op.execute("ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE document_chunks FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON document_chunks")
    op.execute("""
        CREATE POLICY tenant_isolation ON document_chunks
        FOR ALL TO vaultiq_app
        USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON document_chunks TO vaultiq_app")

    # The documents policy was created by the VQ-104 migration as
    #   current_setting('app.current_tenant'::text)      <- no missing_ok
    # and every other tenant table on this schema uses the NULLIF form below.
    #
    # Both parts of the fix are load-bearing, and the first alone is not enough.
    # Without missing_ok Postgres raises "unrecognized configuration parameter"
    # instead of yielding NULL. With missing_ok but without NULLIF, a context
    # that has been set and then committed reverts to the empty string rather
    # than NULL, and ''::uuid raises `invalid input syntax for type uuid: ""`.
    # set_config is transaction-scoped, so that empty-string state is the normal
    # state of a pooled connection between transactions - a request whose first
    # statement is a documents read hits it every time.
    #
    # With NULLIF the expression yields NULL, the comparison is never true, and
    # the query returns zero rows. That is what VQ-102 AC3 asks for - a
    # no-tenant session sees nothing - and it fails closed rather than erroring.
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON documents")
    op.execute("""
        CREATE POLICY tenant_isolation ON documents
        FOR ALL TO vaultiq_app
        USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
    """)


def downgrade() -> None:
    # Restore the VQ-104 policy shape exactly, so the round trip is faithful.
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON documents")
    op.execute("""
        CREATE POLICY tenant_isolation ON documents
        FOR ALL TO vaultiq_app
        USING (tenant_id = current_setting('app.current_tenant'::text)::uuid)
    """)

    # Drop RLS policy
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON document_jobs")
    op.execute("ALTER TABLE document_jobs DISABLE ROW LEVEL SECURITY")

    # document_chunks, mirroring upgrade order. IF EXISTS throughout so a
    # downgrade still succeeds against a database where the table is absent
    # (for example one migrated before this revision created it).
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON document_chunks")
    op.execute("DROP TABLE IF EXISTS document_chunks")

    # Drop constraints and indexes
    op.drop_constraint('uq_document_jobs_document_payload', 'document_jobs', type_='unique')
    op.drop_index('ix_document_jobs_tenant_status_created', table_name='document_jobs')

    # Drop table
    op.drop_table('document_jobs')

    # Drop document columns
    op.drop_column('documents', 'processing_version')
    op.drop_column('documents', 'processing_completed_at')
    op.drop_column('documents', 'processing_started_at')
    op.drop_column('documents', 'processing_error')
    op.drop_column('documents', 'processing_status')

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS job_status")
    op.execute("DROP TYPE IF EXISTS processing_status")