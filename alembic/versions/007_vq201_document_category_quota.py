"""VQ-201: Add document category and enforce storage quota

Revision ID: vq201_document_category_quota
Revises: 006_sessions_tenant_nullable
Create Date: 2026-09-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ENUM

revision = 'vq201_document_category_quota'
down_revision = '006_sessions_tenant_nullable'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create document_category enum
    document_category_enum = ENUM(
        'policy', 'hr', 'sop', 'process', 'other',
        name='document_category',
        create_type=True
    )
    document_category_enum.create(op.get_bind(), checkfirst=True)

    # Add category column to documents table
    op.add_column('documents', sa.Column('category', document_category_enum, nullable=False, server_default='other'))

    # Set default for existing NULL storage_quota_mb values
    op.execute("UPDATE tenants SET storage_quota_mb = 2048 WHERE storage_quota_mb IS NULL")

    # Make storage_quota_mb non-nullable with default 2048 MB
    op.alter_column('tenants', 'storage_quota_mb',
                    existing_type=sa.Integer(),
                    nullable=False,
                    server_default='2048')


def downgrade() -> None:
    # Drop category column
    op.drop_column('documents', 'category')

    # Drop document_category enum
    op.execute('DROP TYPE IF EXISTS document_category')

    # Revert storage_quota_mb to nullable
    op.alter_column('tenants', 'storage_quota_mb',
                    existing_type=sa.Integer(),
                    nullable=True,
                    server_default=None)