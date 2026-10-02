"""VQ-301: Client Admin password reset codes

Revision ID: 27905f137fd4
Revises: 009_platform_access_backport
Create Date: 2026-09-30

A Client Admin resets the password of one of their own organisation's users by
issuing a one-time, time-limited code and handing it over out of band. The user
then sets a new password with it, unauthenticated.

Two decisions here are load-bearing.

CODE HASH, NOT CODE
A reset code is a bearer credential: whoever holds it can set that account's
password. Storing it in plaintext means a database read yields a usable
credential, so the code column holds a SHA-256 hex digest and the plaintext
exists only in the HTTP response. The existing `invites` table stores its codes
in plaintext; that is a pre-existing finding, deliberately not changed here
because altering invite codes is outside this story.

TENANT ID DENORMALISED ONTO THE ROW
The consuming endpoint is unauthenticated, so it has no tenant context, and an
ORM read of `users` under RLS with no context returns nothing. The first
attempt at this endpoint tried to discover the target's tenant from `users`
first and dead-ended exactly there.

Carrying `tenant_id` on the row solves it without widening anything: the caller
reads the single row through a SELECT-only policy keyed on the code hash it
already holds, takes `tenant_id` from that row, and only then sets tenant
context. The context is derived from a row the code itself unlocked, never from
caller input. A SECURITY DEFINER claim function would also work but widens what
a database identity can do, which is the trade the VQ-203 worker design already
declined once.

The public policy is SELECT only. It grants the ability to locate the one row
whose hash the caller possesses and nothing else; the subsequent claim is a
conditional UPDATE that runs under the tenant context taken from the row.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "27905f137fd4"
down_revision: Union[str, None] = "009_platform_access_backport"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reset_codes",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        # Not a client-data column in the usual sense, but it is tenant data and
        # it is what the consuming endpoint uses to establish context, so it is
        # NOT NULL and cascade-deleted with the tenant.
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # SHA-256 hex digest of the code, never the code itself.
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        # The Client Admin who issued it. SET NULL rather than CASCADE so that
        # deactivating an admin does not silently destroy a live reset path.
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Serves the per-user live-code cap (max 3) and the public lookup by hash.
    op.create_index(
        "ix_reset_codes_user_live",
        "reset_codes",
        ["user_id", "used_at", "expires_at"],
    )

    op.execute("ALTER TABLE reset_codes ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE reset_codes FORCE ROW LEVEL SECURITY")

    # The admin path. Same shape as every other tenant table on this schema, and
    # NULLIF is required rather than stylistic: set_config is transaction
    # scoped, so a pooled connection between transactions holds the empty
    # string, and ''::uuid raises instead of matching nothing. This is Known
    # Defect 3.
    op.execute(
        """
        CREATE POLICY tenant_isolation ON reset_codes
        FOR ALL TO vaultiq_app
        USING (
            tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid
        )
        """
    )

    # The public path. SELECT only, and only for the exact hash the caller
    # already holds. It exposes no column other than the row's own, and grants
    # no UPDATE, so it cannot by itself be used to consume a code.
    op.execute(
        """
        CREATE POLICY reset_code_lookup ON reset_codes
        FOR SELECT TO vaultiq_app
        USING (
            code_hash = current_setting('app.reset_code_hash', true)
        )
        """
    )

    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON reset_codes TO vaultiq_app"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS reset_code_lookup ON reset_codes")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON reset_codes")
    op.execute("ALTER TABLE reset_codes DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_reset_codes_user_live", table_name="reset_codes")
    op.drop_table("reset_codes")
