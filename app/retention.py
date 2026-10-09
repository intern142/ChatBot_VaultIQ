"""VQ-402: Retention purge — one tenant at a time, per that tenant's policy.

Nightly on the platform's scheduler (outside the app, no new dependencies):

    0 3 * * * cd /app && python -m app.retention

Each tenant is purged by its own call to vaultiq_purge_tenant_retention(), which
reads that tenant's retention_days and deletes only that tenant's rows older than
the cutoff. There is no statement in this path that can span two tenants.
"""
import asyncio

from sqlalchemy import text

from app.database import AsyncSessionLocal


async def run_retention_once() -> list[dict]:
    """Purge expired audit rows (and conversations, when those tables exist)
    for every tenant. Returns per-tenant, per-table row counts."""
    results: list[dict] = []
    async with AsyncSessionLocal() as session:
        tenants = (
            await session.execute(
                text(
                    "SELECT id, short_code, retention_days "
                    "FROM tenants ORDER BY short_code"
                )
            )
        ).all()
        for tenant_id, short_code, retention_days in tenants:
            rows = (
                await session.execute(
                    text(
                        "SELECT table_name, rows_deleted "
                        "FROM vaultiq_purge_tenant_retention(:tid)"
                    ),
                    {"tid": tenant_id},
                )
            ).all()
            # Commit per tenant: ends the transaction (and the transaction-local
            # tenant context the function sets) before the next tenant runs.
            await session.commit()
            results.append(
                {
                    "tenant_id": str(tenant_id),
                    "short_code": short_code,
                    "retention_days": retention_days,
                    "purged": {table: int(count) for table, count in rows},
                }
            )
    return results


def main() -> None:
    results = asyncio.run(run_retention_once())
    if not results:
        print("retention: no tenants")
        return
    for entry in results:
        purged = ", ".join(
            f"{table}={count}" for table, count in sorted(entry["purged"].items())
        )
        print(
            f"retention: {entry['short_code']} "
            f"(days={entry['retention_days']}) purged {purged or 'nothing'}"
        )


if __name__ == "__main__":
    main()
