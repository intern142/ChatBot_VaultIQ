"""VQ-107: Invite RLS code-lookup policy, audit actor_role as text

Revision ID: 005_invite_code_lookup
Revises: 004_tenant_lifecycle
Create Date: 2026-09-22

"""
from typing import Sequence, Union
from alembic import op

revision: str = "005_invite_code_lookup"
down_revision: Union[str, None] = "004_tenant_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # accept_invite writes actor_role='system', which is not a valid user_role
    # enum value. Store the actor role as free text alongside the enum.
    op.execute("ALTER TABLE audit_logs ALTER COLUMN actor_role TYPE VARCHAR(50)")

    # Public invite acceptance looks an invite up by its (unguessable, 256-bit)
    # code — not by tenant context. Allow a SELECT-only lookup keyed on the exact
    # code via app.invite_accept_code. Writes still require tenant context.
    op.execute(
        """
        CREATE POLICY invite_lookup_by_code ON invites
        FOR SELECT
        USING (code = current_setting('app.invite_accept_code', true))
        """
    )

    # vaultiq_app needs to read tenants for login and invite acceptance.
    op.execute("GRANT SELECT ON tenants TO vaultiq_app")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS invite_lookup_by_code ON invites")
    op.execute("ALTER TABLE audit_logs ALTER COLUMN actor_role TYPE user_role USING actor_role::user_role")
    op.execute("REVOKE SELECT ON tenants FROM vaultiq_app")