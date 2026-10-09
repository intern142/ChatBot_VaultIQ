"""VQ-403: Purge tenants whose offboarding grace period has expired.

Run daily (same ops pattern as other maintenance jobs):

    python -m app.offboard_purge

For every tenant with status='offboarding' and purge_after <= now():
1. call purge_tenant() — the SECURITY DEFINER function that validates the
   grace window itself and hard-deletes every tenant-scoped record in one
   transaction (per-table row counts returned),
2. wipe the tenant's storage directory (files cannot be deleted by SQL),
3. insert a platform-level deletion_reports row (stored outside the tenant),
4. flip the tenant to 'purged'.

Everything for one tenant runs in a single transaction: if the storage wipe
fails, the whole tenant rolls back to 'offboarding' and the next run retries.
Status only reaches 'purged' after the wipe succeeded. Safe to re-run.
"""
import asyncio
import json
import sys
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.services.storage import purge_tenant_storage

GRACE_DAYS = 7


async def purge_due_tenants() -> list[dict[str, Any]]:
    """Purge every tenant past its grace window. Returns one report dict per tenant."""
    purged: list[dict[str, Any]] = []

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                """
                SELECT id, short_code, name, offboarded_by, offboarded_at, purge_after
                FROM tenants
                WHERE status = 'offboarding' AND purge_after <= now()
                ORDER BY purge_after
                """
            )
        )
        due = result.all()

        for row in due:
            tenant_id, short_code, name, initiated_by, initiated_at, purge_after = row

            # 1. Hard-delete all tenant records (validates grace inside the fn)
            counts = (
                await db.execute(
                    text("SELECT purge_tenant(:tid)::text"), {"tid": tenant_id}
                )
            ).scalar()
            rows_deleted: dict[str, int] = json.loads(counts)

            # 2. Wipe files (measured immediately before removal)
            storage = purge_tenant_storage(tenant_id)

            now = datetime.now(timezone.utc)
            report = {
                "rows_deleted": rows_deleted,
                "files_deleted": storage["files_deleted"],
                "bytes_deleted": storage["bytes_deleted"],
                "vacuum_recommended": True,
            }
            backup_flag = {
                "state": "eligible_for_expiry",
                "flagged_at": now.isoformat(),
            }

            # 3. Deletion report — platform-level, survives the purge
            await db.execute(
                text(
                    """
                    INSERT INTO deletion_reports
                        (id, tenant_id, short_code, name, initiated_by,
                         initiated_at, purge_after, purged_at, grace_days,
                         report, backup_flag)
                    VALUES
                        (gen_random_uuid(), :tenant_id, :short_code, :name,
                         :initiated_by, :initiated_at, :purge_after, :purged_at,
                         :grace_days, CAST(:report AS jsonb),
                         CAST(:backup_flag AS jsonb))
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "short_code": short_code,
                    "name": name,
                    "initiated_by": initiated_by,
                    "initiated_at": initiated_at,
                    "purge_after": purge_after,
                    "purged_at": now,
                    "grace_days": GRACE_DAYS,
                    "report": json.dumps(report),
                    "backup_flag": json.dumps(backup_flag),
                },
            )

            # 4. Tombstone (guarded: never clobber a cancelled offboarding)
            await db.execute(
                text(
                    """
                    UPDATE tenants
                    SET status = 'purged', purged_at = :now, updated_at = :now
                    WHERE id = :tid AND status = 'offboarding'
                    """
                ),
                {"tid": tenant_id, "now": now},
            )
            await db.commit()

            purged.append(
                {
                    "tenant_id": str(tenant_id),
                    "short_code": short_code,
                    "report": report,
                }
            )

    return purged


def main() -> int:
    purged = asyncio.run(purge_due_tenants())
    if not purged:
        print("offboard_purge: no tenants due for purge")
        return 0
    for entry in purged:
        print(
            f"offboard_purge: purged {entry['short_code']} "
            f"({entry['tenant_id']}): {json.dumps(entry['report'])}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
