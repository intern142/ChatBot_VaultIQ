"""Grant metadata table access to vaultiq_super_admin

VQ-303: Super Admin console needs read access to metadata tables
(users, documents, audit_logs, indexing_jobs) but NOT content columns.

Revision ID: 011_super_admin_grants
Revises: 010_search_index
Create Date: 2026-10-06

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "011_super_admin_grants"
down_revision: Union[str, None] = "010_search_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Grant SELECT on metadata tables to vaultiq_super_admin
    # These tables have no content columns, only metadata
    
    # users table - grant SELECT on all columns except password_hash
    op.execute("GRANT SELECT (id, tenant_id, email, role, created_at, updated_at, failed_login_attempts, locked_until) ON users TO vaultiq_super_admin")
    
    # documents table - grant SELECT on metadata columns only (not extracted_text)
    op.execute("GRANT SELECT (id, tenant_id, original_filename, stored_filename, mime_type, size_bytes, uploaded_by, created_at, indexed_at) ON documents TO vaultiq_super_admin")
    
    # audit_logs table - grant SELECT on all columns
    op.execute("GRANT SELECT ON audit_logs TO vaultiq_super_admin")
    
    # indexing_jobs table - grant SELECT on all columns
    op.execute("GRANT SELECT ON indexing_jobs TO vaultiq_super_admin")
    
    # tenants table - already has SELECT from VQ-102, but ensure
    op.execute("GRANT SELECT ON tenants TO vaultiq_super_admin")
    
    # Grant USAGE on sequences
    op.execute("GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO vaultiq_super_admin")


def downgrade() -> None:
    op.execute("REVOKE ALL ON users FROM vaultiq_super_admin")
    op.execute("REVOKE ALL ON documents FROM vaultiq_super_admin")
    op.execute("REVOKE ALL ON audit_logs FROM vaultiq_super_admin")
    op.execute("REVOKE ALL ON indexing_jobs FROM vaultiq_super_admin")
    op.execute("REVOKE ALL ON tenants FROM vaultiq_super_admin")
    op.execute("REVOKE USAGE ON ALL SEQUENCES IN SCHEMA public FROM vaultiq_super_admin")