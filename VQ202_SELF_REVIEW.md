# VQ-202 Self-Review

**Branch:** `vq-202-approval-versioning` @ `bad9869`
**Date:** 2026-09-28
**Gate:** 4 — Self-review before PR

---

## Acceptance Criteria Walkthrough

### AC1: Pending → Approved → Archived; only Approved searchable

**Implemented in:** `app/services/approval.py` — `LEGAL_TRANSITIONS`, `searchable_filter()`

**Verified by:** `tests/test_approval.py::test_approval_moves_pending_to_approved`
- New upload → `status = 'pending'`
- Approve → `status = 'approved'` (returns 200, retired=1)
- Re-approve attempt → 409 (illegal transition: only `pending` can be approved)
- Approved → Archive (via superseding) → `status = 'archived'`
- `searchable_filter()` is the **single definition** of searchable: `Document.status == APPROVED`
- Used by: approve service, list searchable endpoint, isolation manifest

**Status:** ✅ Confirmed — one predicate, enforced at state machine level, tested.

---

### AC2: Client Admin approve/reject with optional note

**Implemented in:** 
- `app/routes/documents.py` — `POST /{document_id}/approve`, `POST /{document_id}/reject`
- `app/schemas/document.py` — `ApprovalDecisionRequest(decision_note: str | None)`
- `app/services/approval.py` — `approve_version()`, `reject_version()` store `decision_note`

**Permissions:** `require_roles("client_admin")` on both routes (added to `ROLE_MATRIX`)

**Verified by:** 
- `tests/test_approval.py::test_approve_with_note` / `test_reject_with_note`
- `tests/test_approval.py::test_employee_cannot_approve` (403)
- `tests/test_approval.py::test_client_admin_can_approve` (200)

**Status:** ✅ Confirmed — endpoint exists, permission enforced, note persisted.

---

### AC3: New version creates Pending; approving retires previous atomically

**Implemented in:**
- `app/routes/documents.py` — `POST /documents` accepts optional `replaces` form field (document ID)
- Creates new row with same `document_group_id`, `version_number + 1`, `status = 'pending'`
- `approve_version()` in `app/services/approval.py`:
  1. `FOR UPDATE` on the whole group (serialises concurrent approvals)
  2. `UPDATE ... SET status='archived' WHERE status='approved'` (retire FIRST)
  3. `UPDATE ... SET status='approved' WHERE id = :vid` (promote SECOND)
  4. `tenants.knowledge_base_version++`
  5. Single transaction, one `commit`

**Database invariant:** Partial unique index `uq_documents_one_approved_per_group` on `(document_group_id) WHERE status = 'approved'` — Postgres enforces "at most one approved per group" structurally.

**Verified by:**
- `tests/test_approval.py::test_exactly_one_approved_at_every_point` — re-reads approved set after every step of v1→v2: `{}` → `{v1}` → `{v1}` → `{v2}`
- `tests/test_approval.py::test_partial_unique_index_blocks_two_approved` — hand-written INSERT rejected
- `tests/test_approval.py::test_concurrent_approval_serialised` — two admins, only one wins

**Status:** ✅ Confirmed — atomic retire-before-promote, DB constraint, test proves the invariant.

---

### AC4: Version history visible to Client Admin

**Implemented in:**
- `GET /documents/{document_id}/versions` in `app/routes/documents.py`
- `list_versions()` in `app/services/approval.py` — ordered by `version_number ASC`
- Returns `VersionHistoryResponse(document_group_id, versions[])`

**Permissions:** `client_admin` only (same as approve/reject)

**Verified by:** `tests/test_approval.py::test_version_history_returns_ordered_set`

**Status:** ✅ Confirmed — endpoint exists, correct ordering, permission enforced.

---

### AC5: `tenants.knowledge_base_version` bumped on approve ONLY

**Implemented in:** `approve_version()` — `tenants.knowledge_base_version = knowledge_base_version + 1` inside the approve transaction.

**Not bumped on:** `reject_version()` — explicit comment: "rejecting a pending version does not change the approved set, so bumping would invalidate every cached answer for nothing."

**Verified by:** `tests/test_approval.py::test_reject_does_not_bump_kb_version`

**Status:** ✅ Confirmed — semantic correctness proven by test.

---

## Additional Checks

### Migration & DB Integrity
- Migration `007_vq202_approval_versioning` — up/down round-trip verified
- Partial unique index created: `uq_documents_one_approved_per_group`
- `documents.status` enum, `document_group_id`, `version_number`, `approved_by`, `approved_at`, `decision_note` added
- `tenants.knowledge_base_version` default 1, NOT NULL
- Existing VQ-104 rows backfilled: each gets own `document_group_id`, `version_number=1`, `status='pending'`

### RLS
- `documents` already had FORCE RLS; new columns inherit tenant isolation
- `document_group_id` never spans tenants (group created at first upload)
- Partial index cannot leak: covers groups, groups are tenant-scoped
- `tenants` table has no RLS (platform-managed), `knowledge_base_version` needs none

### Permissions
- Approve, reject, versions: `client_admin` only (added to `ROLE_MATRIX`, isolation manifest updated)
- Employee → 403 (tested)
- Super Admin → 403 on all `/documents/*` (VQ-106 matrix, isolation test covers)
- Cross-tenant: tenant A cannot touch tenant B (isolation suite covers new routes)

### Tests
- `tests/test_approval.py` — 26 tests, all passing
- Full suite: 188 passed (RLS enforced via `vaultiq_app`)

---

## Known Gaps (Honest)

| Item | Status | Note |
|------|--------|------|
| **Gate 6** | ⛔ Cannot execute as written | Brief asks "ask a question and show only v2 content" — search is VQ-203. Stand-in `GET /documents/searchable/approved` exists (no query, no ranking, no content), documented as *not* a search. Needs lead ruling. |
| **Depends on VQ-201** | Unmerged | Both branches add migration `007` against parent `006`. Merge revision needed when VQ-201 lands. This branch does not contain VQ-201's category/quota/OCR. |
| **Prerequisite commit `39a1626`** | Included | Auth-context fix ported from VQ-201. Without it, no tenant user logs in under `vaultiq_app`. |
| **Migration 008 (super-admin RLS)** | Included | Fixes Known Defect #2. Required for Gate 3 green suite. |

---

## Checklist (from `.github/CHECKLIST.md`)

- [x] No tenant boundary crossed
- [x] No outbound network access
- [x] No generated/paraphrased text
- [x] No platform-visible customer content
- [x] All 5 ACs walked and confirmed
- [x] Tests written and green (26/26 approval + 188 full suite)
- [x] Migration up/down verified
- [x] Partial unique index proven by test + hand-written INSERT
- [x] No `db.refresh()` without re-setting tenant context (fixed in admin.py, invite.py, approval.py, documents.py)
- [x] Routes registered in isolation manifest and ROLE_MATRIX

---

## Verdict

All 5 acceptance criteria met. Implementation is complete and tested. Gate 4 self-review complete.

**Next:** Open PR for Gate 5 code review. Gate 6 requires lead decision on stand-in vs. deferred.