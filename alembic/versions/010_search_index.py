"""Tenant-partitioned search index (document_chunks)

VQ-204: Creates a partitioned table for document chunks with tsvector
and vector columns for hybrid search. Each tenant gets its own partition.

Revision ID: 010_search_index
Revises: 006_sessions_tenant_nullable
Create Date: 2026-10-02

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "010_search_index"
down_revision: Union[str, None] = "006_sessions_tenant_nullable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create parent partitioned table
    op.execute("""
        CREATE TABLE document_chunks (
            id uuid NOT NULL DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL,
            document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            chunk_index int NOT NULL,
            content text NOT NULL,
            content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
            embedding vector(384),
            created_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, id)
        ) PARTITION BY LIST (tenant_id)
    """)

    # Indexes on parent (propagate to partitions)
    op.execute("CREATE INDEX ON document_chunks USING GIN (content_tsv)")
    op.execute("CREATE INDEX ON document_chunks USING hnsw (embedding vector_cosine_ops)")
    op.execute("CREATE INDEX ON document_chunks (tenant_id, document_id)")

    # Add indexed_at to documents
    op.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS indexed_at timestamptz")

    # Create indexing_jobs table for async processing
    op.execute("""
        CREATE TABLE indexing_jobs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            status varchar(20) NOT NULL DEFAULT 'pending',
            attempts int NOT NULL DEFAULT 0,
            error text,
            created_at timestamptz NOT NULL DEFAULT now(),
            started_at timestamptz,
            completed_at timestamptz
        )
    """)
    op.execute("CREATE INDEX ON indexing_jobs (tenant_id, status)")
    op.execute("CREATE INDEX ON indexing_jobs (document_id)")

    # RLS on document_chunks
    op.execute("ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE document_chunks FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY document_chunks_tenant_isolation ON document_chunks
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)

    # RLS on indexing_jobs
    op.execute("ALTER TABLE indexing_jobs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE indexing_jobs FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY indexing_jobs_tenant_isolation ON indexing_jobs
        USING (tenant_id = current_setting('app.current_tenant', true)::uuid)
    """)

    # Grant permissions to vaultiq_app
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON document_chunks TO vaultiq_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON indexing_jobs TO vaultiq_app")
    op.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO vaultiq_app")

    # Grant to vaultiq_super_admin for partition management
    op.execute("GRANT CREATE ON SCHEMA public TO vaultiq_super_admin")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON document_chunks TO vaultiq_super_admin")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON indexing_jobs TO vaultiq_super_admin")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS indexing_jobs")
    op.execute("DROP TABLE IF EXISTS document_chunks")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS indexed_at")
    op.execute("DROP EXTENSION IF EXISTS vector")