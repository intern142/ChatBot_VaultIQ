"""VQ-403: Tenant offboarding — grace columns, deletion_reports, purge function

Revision ID: 007_offboarding
Revises: 006_sessions_tenant_nullable
Create Date: 2026-10-08

"""
from typing import Sequence, Union
from alembic import op


revision: str = "007_offboarding"
down_revision: Union[str, None] = "006_sessions_tenant_nullable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Derived search artefacts and jobs. Guarded two ways inside purge_tenant():
# the table must exist (to_regclass) AND it must carry a tenant_id column
# (information_schema) before it is purged — so future tables without
# tenant_id, or tables that don't exist yet, can never break the purge.
DERIVED_TENANT_TABLES = [
    "text_chunks",
    "embeddings",
    "document_versions",
    "conversations",
    "messages",
    "feedback",
    "cached_answers",
    "ingestion_jobs",
]


def upgrade() -> None:
    # --- Offboarding columns on tenants ---
    op.execute("ALTER TABLE tenants ADD COLUMN offboarded_at TIMESTAMPTZ")
    op.execute(
        "ALTER TABLE tenants ADD COLUMN offboarded_by UUID "
        "REFERENCES users(id) ON DELETE SET NULL"
    )
    op.execute("ALTER TABLE tenants ADD COLUMN purge_after TIMESTAMPTZ")
    op.execute("ALTER TABLE tenants ADD COLUMN purged_at TIMESTAMPTZ")

    # --- deletion_reports: platform-level record stored OUTSIDE the tenant ---
    # Deliberately: no RLS (not tenant-scoped), no vaultiq_app grant.
    # Readable by platform operators only (super_admin role), survives the
    # purge of the tenant it describes (FK points at the tombstone tenant row).
    op.execute(
        """
        CREATE TABLE deletion_reports (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            short_code VARCHAR(50) NOT NULL,
            name VARCHAR(255) NOT NULL,
            initiated_by UUID REFERENCES users(id),
            initiated_at TIMESTAMPTZ NOT NULL,
            purge_after TIMESTAMPTZ NOT NULL,
            purged_at TIMESTAMPTZ NOT NULL,
            grace_days INTEGER NOT NULL,
            report JSONB NOT NULL DEFAULT '{}',
            backup_flag JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX ix_deletion_reports_tenant_id ON deletion_reports(tenant_id)")
    op.execute("GRANT SELECT ON deletion_reports TO vaultiq_super_admin")

    # --- purge_tenant: the only lawful purge path ---
    # SECURITY DEFINER (owner = vaultiq, superuser) so it can delete audit rows
    # that application roles are REVOKE'd from deleting. Grace is validated
    # INSIDE the function — an app session, however compromised, cannot purge
    # a tenant before purge_after. Single transaction: all-or-nothing.
    tables = "', '".join(DERIVED_TENANT_TABLES)
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION purge_tenant(p_tenant_id uuid)
        RETURNS jsonb
        LANGUAGE plpgsql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        AS $function$
        DECLARE
            v_tenant tenants%ROWTYPE;
            v_counts jsonb := '{{}}'::jsonb;
            v_n bigint;
            v_table text;
        BEGIN
            SELECT * INTO v_tenant FROM tenants WHERE id = p_tenant_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'purge_tenant: tenant % not found', p_tenant_id;
            END IF;
            IF v_tenant.status <> 'offboarding'
               OR v_tenant.purge_after IS NULL
               OR v_tenant.purge_after > now() THEN
                RAISE EXCEPTION 'purge_tenant: tenant % not eligible for purge (status=%, purge_after=%)',
                    p_tenant_id, v_tenant.status, v_tenant.purge_after;
            END IF;

            -- Hard deletes in FK-safe order: audit rows and sessions/invites/
            -- documents all reference users, so users go last.
            FOREACH v_table IN ARRAY ARRAY['audit_logs','invites','sessions','documents','users'] LOOP
                EXECUTE format('DELETE FROM %I WHERE tenant_id = $1', v_table) USING p_tenant_id;
                GET DIAGNOSTICS v_n = ROW_COUNT;
                v_counts := v_counts || jsonb_build_object(v_table, v_n);
            END LOOP;

            -- Derived artefacts: guarded (table exists AND has tenant_id)
            FOREACH v_table IN ARRAY ARRAY['{tables}'] LOOP
                IF to_regclass('public.' || v_table) IS NOT NULL
                   AND EXISTS (
                       SELECT 1 FROM information_schema.columns
                       WHERE table_schema = 'public'
                         AND table_name = v_table
                         AND column_name = 'tenant_id'
                   ) THEN
                    EXECUTE format('DELETE FROM %I WHERE tenant_id = $1', v_table) USING p_tenant_id;
                    GET DIAGNOSTICS v_n = ROW_COUNT;
                    v_counts := v_counts || jsonb_build_object(v_table, v_n);
                END IF;
            END LOOP;

            RETURN v_counts;
        END;
        $function$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION purge_tenant(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION purge_tenant(uuid) TO vaultiq_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS purge_tenant(uuid)")
    op.execute("DROP TABLE IF EXISTS deletion_reports")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS purged_at")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS purge_after")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS offboarded_by")
    op.execute("ALTER TABLE tenants DROP COLUMN IF EXISTS offboarded_at")
