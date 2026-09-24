"""VQ-104: Add documents table for per-tenant storage

Revision ID: d9ecec7d2e04
Revises: 002_add_sessions
Create Date: 2026-09-17 18:32:26.693630

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd9ecec7d2e04'
down_revision: Union[str, None] = '002_add_sessions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('original_filename', sa.Text(), nullable=False),
        sa.Column('stored_filename', sa.Text(), nullable=False),
        sa.Column('mime_type', sa.Text(), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('uploaded_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_documents_tenant', 'documents', ['tenant_id', 'created_at'], unique=False)

    # Enable RLS
    op.execute('ALTER TABLE documents ENABLE ROW LEVEL SECURITY')

    # Create RLS policy
    op.execute("""
        CREATE POLICY tenant_isolation ON documents
        USING (tenant_id = current_setting('app.current_tenant')::uuid)
    """)


def downgrade() -> None:
    op.execute('DROP POLICY IF EXISTS tenant_isolation ON documents')
    op.execute('ALTER TABLE documents DISABLE ROW LEVEL SECURITY')
    op.drop_index('ix_documents_tenant', table_name='documents')
    op.drop_table('documents')