"""VQ-301: Client Admin user management - deactivation and invite roles

Revision ID: c4d81f0a7e26
Revises: 27905f137fd4
Create Date: 2026-10-01

Two columns, for two of the five remaining VQ-301 criteria.

users.is_active
    AC3 deactivate/reactivate. A boolean, not a status enum: a user is active or
    it is not. "Pending invite" is a row in `invites`, not a state of a user, and
    a three-value enum would mean every read of `users` had to decide what to do
    with the third value.

    NOT NULL, so no third state can exist: no NULL, no NULL-means-something.

    DEFAULT true is kept deliberately. It is what makes the migration safe on a
    populated database (every existing row is active, no backfill statement, no
    window where the column does not exist), and it is the correct value for a
    row that arrives without the column - an unflagged user is an active user,
    which is exactly the behaviour of every version of this system before the
    column existed.

    The direction of the default is the security question, and `true` is the safe
    one: the rows it gets wrong are rows created by a path that forgot to write
    the flag, and such a user being active is the pre-existing behaviour rather
    than a new hole. A default of false would have made every forgotten insert
    fail closed, at the cost of needing a backfill and a real risk of mass-
    deactivating accounts on a partial deploy.

invites.role
    AC1 invite one user at a chosen role. VQ-107's invites could only ever make a
    client_admin, and `/invite/accept` hardcoded that role. The accept endpoint now
    creates the user at `invite.role`, and the "tenant already has a Client Admin"
    refusal applies only when the invite asks for client_admin - which is exactly
    the bootstrap case VQ-107 AC3 was written about, so that criterion keeps
    working unchanged.

    DEFAULT 'client_admin' for the same reason as is_active: every invite row that
    exists today keeps its current meaning, and an invite created without the
    column means client_admin, which is what it meant before.

    VARCHAR, not the `user_role` enum, for the same reason `audit_logs.actor_role`
    is text (migration 004). Adding a value to a live Postgres enum requires ALTER
    TYPE outside a transaction, which Alembic will not give us inside a migration.
    Choosing text does leave the column free to hold anything, so the two permitted
    values are pinned by a CHECK constraint in the same migration. The application
    repeats the check in app/schemas/user.py because a 422 naming the bad role is a
    better answer than an integrity error, and because super_admin must be refused
    before anything is written.

No RLS changes. Both columns live on tables that already have FORCE RLS and a
tenant_isolation policy; a new column is not a new visibility rule. `is_active` in
particular must not become a security boundary on its own - it is enforced in
app/routes/auth.py (login) and app/auth/dependencies.py (existing tokens), both of
which run under the tenant context RLS already requires.

No index on either column. `invites.role` is never read in a WHERE clause, and
`users.is_active` is only ever read together with `tenant_id`, which the existing
uq_user_email_per_tenant index already leads with. A standalone index on either
would be write cost for no query.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c4d81f0a7e26"
down_revision: Union[str, None] = "27905f137fd4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "invites",
        sa.Column(
            "role",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'client_admin'"),
        ),
    )

    # The two-value restriction enforced by the database, not only by the
    # endpoint's schema validation.
    #
    # VARCHAR was chosen over the user_role enum for migration reasons, which
    # leaves the column free to hold anything. That freedom is the thing to close
    # off: `super_admin` must not be insertable into an invites row by any writer,
    # including a future one that forgets to call the Pydantic validator, because
    # `/invite/accept` creates a user at `invite.role` and a super_admin created
    # through a tenant-scoped endpoint escapes tenant scoping entirely.
    #
    # A CHECK rather than the enum, because the point of avoiding the enum was to
    # avoid ALTER TYPE on a live database, and reintroducing it here would undo
    # that. The downgrade drops the constraint with the column.
    op.create_check_constraint(
        "ck_invites_role_is_tenant_role",
        "invites",
        "role IN ('employee', 'client_admin')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_invites_role_is_tenant_role", "invites", type_="check")
    op.drop_column("invites", "role")
    op.drop_column("users", "is_active")