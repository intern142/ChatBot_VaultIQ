from alembic import op
import sqlalchemy as sa


revision = '008_document_text_extraction'
down_revision = 'vq201_document_category_quota'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('documents', sa.Column('extracted_text', sa.Text(), nullable=True))
    op.add_column('documents', sa.Column('extraction_method', sa.String(length=20), nullable=True))
    op.add_column('documents', sa.Column('extraction_status', sa.String(length=20), nullable=True))
    op.add_column('documents', sa.Column('extraction_page_count', sa.Integer(), nullable=True))
    op.add_column(
        'documents',
        sa.Column('extraction_truncated', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade():
    op.drop_column('documents', 'extraction_truncated')
    op.drop_column('documents', 'extraction_page_count')
    op.drop_column('documents', 'extraction_status')
    op.drop_column('documents', 'extraction_method')
    op.drop_column('documents', 'extracted_text')
