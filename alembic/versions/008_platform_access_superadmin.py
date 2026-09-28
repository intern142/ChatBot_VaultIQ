"""Platform access for Super Admin accounts.

Known Defect #2. VQ-101 AC3 requires platform (Super Admin) accounts to have no
tenant, so those rows exist with tenant_id IS NULL. The policies on users and
sessions were bare

    tenant_id = current_setting('app.current_tenant', true)::uuid

with no branch for tenant_id IS NULL, so under vaultiq_app - the real production
identity - platform rows were unreachable. Reproduced before this migration:

    POST /auth/login organisation_code=SUPER   -> 401 (user row invisible)
    INSERT INTO sessions (user_id, tenant_id=NULL) -> InsufficientPrivilegeError

Super Admin is the only role that can create a tenant, so this blocked tenant
lifecycle, VQ-201 Gate 6 and VQ-202 Gate 3.

The fix is a second, PERMISSIVE policy per table. Postgres ORs permissive
policies together, so a row is visible when it satisfies ANY of them. The two
policies here are disjoint: the tenant policy requires tenant_id to equal the
context, the platform policy requires tenant_id IS NULL. They can never both be
true for the same row.

The platform policy is gated on app.platform_access = 'on', which the application
sets only on platform auth paths. Four conditions must all hold:

  1. tenant_id IS NULL          - it is a platform row
  2. role = 'super_admin'       - and it is a platform operator, not some other
                                   tenantless row
  3. app.platform_access = 'on' - the application asked for platform access
  4. no tenant in context       - app.current_tenant is unset or empty

Condition 4 is deliberate defence in depth. If a future bug ever set both the
tenant context and the platform flag on the same request, this policy would go
false and the request would see zero rows rather than seeing platform rows *and*
tenant rows together. The failure mode is a broken request, not a leak.

Consequences of the gate, which are the properties we need:

  - Tenant request (current_tenant=X, platform_access unset): platform rows are
    invisible because 3 is false. A tenant can never see or become a platform
    operator.
  - Platform request (platform_access=on, current_tenant empty): the tenant
    policy's current_setting returns NULL/empty so tenant_id = NULL is never
    true, and platform rows match. A Super Admin sees platform accounts and
    nothing else - no tenant's documents, users or answers. Rule #4 holds.
  - Neither set: both policies false, zero rows.

WITH CHECK is intentionally omitted, exactly as the existing tenant_isolation
policies do. Postgres then applies USING to inserts too, which is what makes the
NULL-tenant session INSERT work rather than failing as it did before.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "008_platform_access_superadmin"
down_revision: Union[str, None] = "007_vq202_approval_versioning"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# users carries role, so the policy can require role = 'super_admin' directly.
# sessions has no role column, so there the tenant_id IS NULL test is the whole
# discriminator. That is sufficient because a session row inherits tenant_id
# from its user, and every non-platform user has a tenant by VQ-101 AC2: a
# session with tenant_id IS NULL is a platform session by construction. It
# cannot be used to reach tenant data, because a token's own jti resolves to its
# own session row, and a tenant user's row has a tenant_id and so does not match
# this policy.
SCOPED_TABLES = ("users", "sessions", "documents", "invites", "audit_logs")

# The platform context is established by clearing app.current_tenant to ''. That
# breaks the existing tenant_isolation policies, which cast the setting straight
# to uuid:
#
#     tenant_id = current_setting('app.current_tenant', true)::uuid
#
# ''::uuid is invalid input syntax, so on a platform request - which clears the
# tenant - evaluating that policy raises "invalid input syntax for type uuid"
# and aborts the transaction. That is the same class of defect as the missing_ok
# bug already fixed on documents: the cast throws instead of yielding no rows.
#
# Wrapping the setting in NULLIF turns '' into NULL before the cast, so
# tenant_id = NULL is NULL, which is not true, and the policy correctly reports
# no tenant rows. It fails closed rather than erroring, in both the empty and the
# unset cases, so the policy is now correct for platform requests as well as
# tenant ones.
TENANT_POLICY = """
CREATE POLICY tenant_isolation ON {table}
    FOR ALL TO vaultiq_app
    USING (tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid)
"""

POLICIES = {
    "users": """
CREATE POLICY platform_account_access ON users
    FOR ALL TO vaultiq_app
    USING (
        tenant_id IS NULL
        AND role = 'super_admin'
        AND current_setting('app.platform_access', true) = 'on'
        AND COALESCE(NULLIF(current_setting('app.current_tenant', true), ''), '') = ''
    )
""",
    "sessions": """
CREATE POLICY platform_account_access ON sessions
    FOR ALL TO vaultiq_app
    USING (
        tenant_id IS NULL
        AND current_setting('app.platform_access', true) = 'on'
        AND COALESCE(NULLIF(current_setting('app.current_tenant', true), ''), '') = ''
    )
""",
}


def upgrade() -> None:
    for table in SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(TENANT_POLICY.format(table=table))
    for table, sql in POLICIES.items():
        op.execute(sql)


def downgrade() -> None:
    for table in POLICIES:
        op.execute(f"DROP POLICY IF EXISTS platform_account_access ON {table}")
    for table in SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} FOR ALL TO vaultiq_app "
            "USING (tenant_id = current_setting('app.current_tenant', true)::uuid)"
        )
