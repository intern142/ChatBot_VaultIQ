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

# revision identifiers, used by Alembic.
revision: str = '160ccbed24a5'
down_revision: Union[str, None] = 'a1340d9f596a'
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


def downgrade() -> None:
    # Drop RLS policy
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON document_jobs")
    op.execute("ALTER TABLE document_jobs DISABLE ROW LEVEL SECURITY")

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