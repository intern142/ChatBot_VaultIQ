"""VQ-402: Shared audit-trail writer.

Single extension point for the compliance trail. Every story that adds an
operation calls write_audit_log() and its action appears in the tenant's export.

Fail-closed by design: if the audit insert fails, the request fails ΓÇö a trail
that silently skips entries is worse than a 500.
"""
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import set_tenant_context
from app.models.audit_log import AuditLog


async def write_audit_log(
    db: AsyncSession,
    tenant_id: UUID,
    actor_user_id: Optional[UUID],
    actor_role: str,
    action: str,
    target_type: str,
    target_id: UUID,
    details: dict[str, Any],
) -> AuditLog:
    """Write one audit row for exactly one tenant.

    Sets the tenant context itself (SET LOCAL) so the insert passes FORCE RLS
    under the vaultiq_app identity ΓÇö callers cannot forget it.
    """
    await set_tenant_context(db, str(tenant_id))
    audit = AuditLog(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        actor_role=actor_role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )
    db.add(audit)
    await db.flush()
    return audit
