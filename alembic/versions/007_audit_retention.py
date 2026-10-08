"""VQ-402: Audit trail hardening + per-tenant retention

- tenants.retention_days: the tenant's own retention policy
- REVOKE UPDATE/DELETE on audit_logs from the application identities: the trail
  can only ever be INSERTed/SELECTed by the application; the only lawful delete
  path is the retention function below
- vaultiq_purge_tenant_retention(tenant): SECURITY DEFINER purge of rows older
  than THAT tenant's own retention_days, scoped to that tenant only. Also purges
  conversations/messages when those tables exist (QA story).

Revision ID: 007_audit_retention
Revises: 006_sessions_tenant_nullable
Create Date: 2026-10-08

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "007_audit_retention"
down_revision: Union[str, None] = "006_sessions_tenant_nullable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PURGE_FUNCTION = """
CREATE FUNCTION vaultiq_purge_tenant_retention(p_tenant_id uuid)
RETURNS TABLE(table_name text, rows_deleted bigint)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_days integer;
    v_cutoff timestamptz;
    v_table text;
    v_count bigint;
BEGIN
    SELECT t.retention_days INTO v_days FROM tenants t WHERE t.id = p_tenant_id;
    IF v_days IS NULL THEN
        RAISE EXCEPTION 'vaultiq_purge_tenant_retention: unknown tenant %', p_tenant_id;
    END IF;
    v_cutoff := now() - make_interval(days => v_days);

    -- Make FORCE RLS on audit_logs pass even if the function owner is ever
    -- changed to a non-BYPASSRLS role: context is transaction-local.
    PERFORM set_config('app.current_tenant', p_tenant_id::text, true);

    DELETE FROM audit_logs a
        WHERE a.tenant_id = p_tenant_id AND a.created_at < v_cutoff;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    table_name := 'audit_logs';
    rows_deleted := v_count;
    RETURN NEXT;

    -- Conversations/messages: purge when the QA story's tables exist AND carry
    -- the tenant_id + created_at columns this predicate needs.
    FOREACH v_table IN ARRAY ARRAY['conversations', 'messages'] LOOP
        IF to_regclass('public.' || v_table) IS NOT NULL
           AND EXISTS (SELECT 1 FROM information_schema.columns c
                       WHERE c.table_schema = 'public' AND c.table_name = v_table
                         AND c.column_name = 'tenant_id')
           AND EXISTS (SELECT 1 FROM information_schema.columns c
                       WHERE c.table_schema = 'public' AND c.table_name = v_table
                         AND c.column_name = 'created_at') THEN
            EXECUTE format(
                'DELETE FROM public.%I WHERE tenant_id = $1 AND created_at < $2',
                v_table
            ) USING p_tenant_id, v_cutoff;
            GET DIAGNOSTICS v_count = ROW_COUNT;
            table_name := v_table;
            rows_deleted := v_count;
            RETURN NEXT;
        END IF;
    END LOOP;
END;
$$
"""


def upgrade() -> None:
    # --- Per-tenant retention policy ---
    op.execute("""
        ALTER TABLE tenants
        ADD COLUMN retention_days INTEGER NOT NULL DEFAULT 365
        CONSTRAINT chk_tenants_retention_days CHECK (retention_days >= 1)
    """)

    # --- AC2: the application identity can never edit or delete audit rows ---
    # Grants on audit_logs were already SELECT, INSERT only (migration 004);
    # the explicit REVOKE locks the intent against any future GRANT ALL.
    op.execute("REVOKE UPDATE, DELETE ON audit_logs FROM vaultiq_app")
    op.execute("REVOKE UPDATE, DELETE ON audit_logs FROM vaultiq_super_admin")

    # --- The only lawful delete path: single-tenant, policy-driven purge ---
    op.execute(PURGE_FUNCTION)
    # Default function ACL grants EXECUTE to PUBLIC — take that back.
    op.execute("REVOKE ALL ON FUNCTION vaultiq_purge_tenant_retention(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION vaultiq_purge_tenant_retention(uuid) TO vaultiq_app")


def downgrade() -> None:
    op.execute("REVOKE EXECUTE ON FUNCTION vaultiq_purge_tenant_retention(uuid) FROM vaultiq_app")
    op.execute("DROP FUNCTION IF EXISTS vaultiq_purge_tenant_retention(uuid)")

    # Restore the pre-VQ-402 grant set exactly as migration 004 defined it
    op.execute("GRANT SELECT, INSERT ON audit_logs TO vaultiq_app")

    op.execute("ALTER TABLE tenants DROP CONSTRAINT chk_tenants_retention_days")
    op.execute("ALTER TABLE tenants DROP COLUMN retention_days")
