"""Audit trail writes.

One implementation, shared by `app/routes/admin.py` (VQ-107 tenant lifecycle,
super_admin) and `app/routes/users.py` (VQ-301 user management, client_admin).

This lived as two near-identical private helpers, one per router. That is a bad
place to have a duplicate: an audit write is security-relevant, because the row's
`tenant_id` is what RLS scopes the read of, and a future change made in one copy
and not the other would silently apply to half the trail.

The caller is responsible for having set the tenant context - `set_tenant_context`
or `set_platform_context` - because `audit_logs` has FORCE RLS and a
`tenant_isolation` policy. The tenant_id argument is therefore not what grants
the write; it is only correct if it came from the verified token.
"""
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def write_audit_log(
    db: AsyncSession,
    tenant_id: UUID,
    actor_user_id: Optional[UUID],
    actor_role: str,
    action: str,
    target_type: str,
    target_id: Optional[UUID],
    details: dict[str, Any],
) -> AuditLog:
    """Write one audit entry and flush it.

    Flushed rather than committed: the caller owns the transaction, so the audit
    row commits or rolls back with the change it describes. A separate commit
    would leave audit entries describing writes that never happened.
    """
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