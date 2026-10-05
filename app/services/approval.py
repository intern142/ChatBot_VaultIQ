"""VQ-202: the approval state machine.

All legal state transitions live here, not in route handlers, so there is one
definition of "approved" and one place that can be wrong.

The invariant AC3 asks for is that there is never a moment where both or neither
version of a logical document is searchable. Two things enforce it:

  1. uq_documents_one_approved_per_group, a partial unique index, makes "both"
     impossible at the database level regardless of what the application does.
  2. The transaction in approve_version(), which retires the outgoing version
     BEFORE promoting the incoming one, makes "neither" impossible for any
     concurrent reader. An outside reader sees the pre-commit snapshot (old
     approved) or the post-commit state (new approved) - never a gap.

FOR UPDATE serialises two client admins approving two different versions at the
same time, so only one can win.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import set_tenant_context
from app.models.document import Document
from app.models.tenant import Tenant

PENDING = "pending"
APPROVED = "approved"
ARCHIVED = "archived"
REJECTED = "rejected"

# Which transitions the state machine permits. Anything not listed is refused.
LEGAL_TRANSITIONS = {
    PENDING: {APPROVED, REJECTED},
    APPROVED: {ARCHIVED},
    ARCHIVED: set(),
    REJECTED: set(),
}

TERMINAL_STATES = {ARCHIVED, REJECTED}


class ApprovalError(Exception):
    """Refused transition. Carries the HTTP status the route should return."""

    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def searchable_filter():
    """The one definition of 'takes part in search'.

    Used by every read path so search, listing and the approval logic can never
    disagree about what is searchable.
    """
    return Document.status == APPROVED


async def approve_version(
    db: AsyncSession,
    document_id: uuid.UUID,
    tenant_id: uuid.UUID,
    approver_id: uuid.UUID,
    note: str | None = None,
) -> tuple[Document, int]:
    """Approve a pending version, retiring the outgoing one in the same commit.

    Returns the approved version and how many outgoing versions were retired, so
    callers and tests can assert the swap actually happened.
    """
    version = await _lock_and_load(db, document_id, tenant_id)

    if version.status != PENDING:
        raise ApprovalError(
            f"cannot approve a document in status {version.status!r}; "
            f"only {PENDING!r} can be approved"
        )

    # Lock the whole group. Two admins approving v2 and v3 concurrently must not
    # both succeed, and the partial unique index would otherwise reject the second
    # with an opaque constraint violation instead of a clean refusal.
    await db.execute(
        select(Document)
        .where(
            Document.document_group_id == version.document_group_id,
            Document.tenant_id == tenant_id,
        )
        .with_for_update()
    )

    # Retire first, promote second. The reverse order would transiently hold two
    # approved versions in the group and trip the partial unique index mid-
    # transaction.
    result = await db.execute(
        update(Document)
        .where(
            Document.document_group_id == version.document_group_id,
            Document.tenant_id == tenant_id,
            Document.status == APPROVED,
        )
        .values(status=ARCHIVED)
    )
    retired = result.rowcount

    version.status = APPROVED
    version.approved_by = approver_id
    version.approved_at = datetime.now(timezone.utc)
    version.decision_note = note

    await db.execute(
        update(Tenant)
        .where(Tenant.id == tenant_id)
        .values(knowledge_base_version=Tenant.knowledge_base_version + 1)
    )

    await db.commit()
    await _refresh(db, version, tenant_id)
    return version, retired


async def reject_version(
    db: AsyncSession,
    document_id: uuid.UUID,
    tenant_id: uuid.UUID,
    approver_id: uuid.UUID,
    note: str | None = None,
) -> Document:
    version = await _lock_and_load(db, document_id, tenant_id)

    if version.status != PENDING:
        raise ApprovalError(
            f"cannot reject a document in status {version.status!r}; "
            f"only {PENDING!r} can be rejected"
        )

    version.status = REJECTED
    version.approved_by = approver_id
    version.approved_at = datetime.now(timezone.utc)
    version.decision_note = note

    # No knowledge_base_version bump: rejecting a pending version does not change
    # the approved set, so invalidating every cached answer would be wrong.
    await db.commit()
    await _refresh(db, version, tenant_id)
    return version


async def list_versions(
    db: AsyncSession,
    document_group_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> list[Document]:
    result = await db.execute(
        select(Document)
        .where(
            Document.document_group_id == document_group_id,
            Document.tenant_id == tenant_id,
        )
        .order_by(Document.version_number.asc())
    )
    return list(result.scalars().all())


async def _refresh(db: AsyncSession, version: Document, tenant_id: uuid.UUID) -> None:
    """Reload a row after commit, re-establishing the tenant context first.

    set_tenant_context is transaction-scoped, so commit discarded it. A refresh
    without context hits the documents policy with no tenant set, reads zero rows,
    and SQLAlchemy raises "Could not refresh instance".
    """
    await set_tenant_context(db, str(tenant_id))
    await db.refresh(version)


async def _lock_and_load(
    db: AsyncSession, document_id: uuid.UUID, tenant_id: uuid.UUID
) -> Document:
    """Load a version for update, scoped to the tenant.

    The tenant_id predicate is not decoration: RLS already refuses cross-tenant
    rows, but the query must not depend on that alone to decide who owns a
    document.
    """
    result = await db.execute(
        select(Document)
        .where(Document.id == document_id, Document.tenant_id == tenant_id)
        .with_for_update()
    )
    version = result.scalar_one_or_none()
    if not version:
        # Same response as a genuinely missing document, so tenant B cannot learn
        # that tenant A's document id exists.
        raise ApprovalError("Document not found", status_code=404)
    return version
