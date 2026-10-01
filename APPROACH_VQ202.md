# VQ-202 — Approval workflow and document versions (Approach Note)

Branch: `vq-202-approval-versioning` · Base: `main` @ `9e5ecc8`
Sprint 3 · P0 · 5pt · Depends on VQ-201 (HX-201, not yet merged — see Blockers)

## Objective

Only documents a Client Admin has approved can ever answer a question, and replacing
a document never leaves two versions answering at once.

## Acceptance criteria → how each is met

| # | Criterion | Mechanism |
|---|-----------|-----------|
| 1 | Pending → Approved → Archived; only Approved takes part in search | `documents.status` enum; a single `searchable` predicate, one definition |
| 2 | Client Admin can approve or reject with an optional note | `POST /documents/{id}/approve` and `/reject`, `client_admin` only, `decision_note` nullable |
| 3 | New version creates a Pending version; approving retires the previous at the same moment | `document_group_id` + `version_number`; single transaction, DB-enforced single-approved invariant |
| 4 | Version history visible to Client Admin | `GET /documents/{id}/versions` |
| 5 | Per-tenant knowledge base version changes when the approved set changes | `tenants.knowledge_base_version`, bumped inside the approve transaction |

## Versioning model

`documents` stays the row that holds one uploaded file. A **logical document** is the
set of rows sharing a `document_group_id`.

- First upload generates a fresh `document_group_id`, `version_number = 1`.
- Uploading a new version of an existing document reuses the group and increments
  `version_number`. The new row is born `pending`.
- Existing VQ-104 rows each get their own group of one on migration.

**Why not a separate `document_versions` table.** It is the cleaner relational shape,
but it would require migrating every existing document row into a (parent, version)
pair, moving the storage path, RLS policy and every VQ-104 endpoint onto the new table,
and re-doing the tenant-isolation proof VQ-110 just established. The denormalised group
id costs one extra column and keeps all of that intact. If search (VQ-203) later needs
per-document metadata, a parent table can be introduced then with a real reason.

## State machine

```
                 upload
                   │
                   ▼
              ┌─────────┐   reject   ┌──────────┐
              │ pending │───────────▶│ rejected │ (terminal)
              └─────────┘            └──────────┘
                   │ approve
                   ▼
              ┌─────────┐  superseded  ┌──────────┐
              │ approved│─────────────▶│ archived │ (terminal)
              └─────────┘              └──────────┘
```

- `rejected` and `archived` are terminal. An archived version is never resurrected;
  uploading v3 creates a new pending row alongside the archived v1/v2 history.
- Only `approved` is searchable.
- Legal transitions are enforced in one place (`services/approval.py`), not scattered
  across route handlers.

## The core invariant: never both, never neither

AC3 requires that there is **no moment where both or neither** versions are searchable.
Two protections, one in each layer:

**1. Database — structural, not procedural.**
```sql
CREATE UNIQUE INDEX uq_documents_one_approved_per_group
    ON documents (document_group_id) WHERE status = 'approved';
```
At most one approved version per logical document, enforced by Postgres. A bug in
application code cannot produce two approved versions, and the isolation suite proves
the constraint holds.

**2. Application — one transaction, ordered statements.**
```sql
BEGIN;
  SELECT ... FROM documents
   WHERE document_group_id = :gid AND status IN ('approved','pending')
   FOR UPDATE;                      -- serialises concurrent approvals
  UPDATE documents SET status='archived'  WHERE ...;   -- retire old FIRST
  UPDATE documents SET status='approved'  WHERE id = :vid;  -- then promote new
  UPDATE tenants SET knowledge_base_version = knowledge_base_version + 1 WHERE id = :tid;
COMMIT;
```

Ordering matters: retiring the old version before promoting the new one is what keeps
the partial unique index satisfied at every statement inside the transaction. An outside
reader sees the pre-commit snapshot (old approved) or the post-commit state (new
approved) — never both, never neither.

`FOR UPDATE` is what stops two client admins approving v2 and v3 simultaneously from
both winning.

## Transaction boundaries

- **Approve**: one transaction, covering the row lock, both UPDATEs and the
  `knowledge_base_version` bump. Nothing is written outside it.
- **Reject**: one transaction, no version bump (the approved set did not change).
- **Upload a new version**: one transaction. The group row and version number are
  resolved under `FOR UPDATE` so two concurrent uploads cannot claim the same number.

## Knowledge base version

`tenants.knowledge_base_version INTEGER NOT NULL DEFAULT 1`.

Bumped **only on approve**. Approving v2 changes the approved set (v1 out, v2 in).
Rejecting a pending version does not — the approved set is untouched — so bumping there
would invalidate every cached answer for no reason. The column exists so VQ-203 can
invalidate cached answers without rescanning the corpus.

## RLS

`documents` already carries FORCE RLS on tenant. The new columns ride on the existing
policy; `document_group_id` is tenant-scoped by construction because every row in the
group has the same `tenant_id` as the first. A partial unique index cannot be used to
leak across tenants: the index covers groups, and a group never spans tenants.

`tenants.knowledge_base_version` is a column on a table with no RLS (platform-managed),
so it needs none.

## Permissions

Approve, reject and version history are `client_admin` only, added to `ROLE_MATRIX`.
Employees cannot approve — that is the whole control. Super Admin remains denied on all
`/documents/*` per VQ-106.

## Tests

1. New document is born `pending`; not searchable.
2. Approve moves it to `approved`; becomes searchable; `knowledge_base_version` +1.
3. Reject moves to `rejected`; never searchable; version **not** bumped.
4. Approving a non-pending version is refused (illegal transition).
5. Upload v2 → group and version number correct, v2 pending, v1 still approved.
6. **Approving v2 retires v1 atomically** — assert after the operation that exactly one
   approved version exists in the group, and that the partial unique index rejects a
   hand-made attempt to have two.
7. Concurrent approval of v2 and v3 → exactly one succeeds (row lock).
8. Version history returns the full ordered set.
9. Employee cannot approve (403). Client Admin can.
10. Cross-tenant: tenant A cannot approve/read tenant B's document.
11. Migration up/down round-trip.

## Blockers and open questions

**Gate 6 cannot be executed as written.** It asks to "ask a question" and show only v2
content. There is no question/search endpoint — search is VQ-203. Options: reword Gate 6
to assert on the set of approved text, or accept a stand-in read endpoint that is
explicitly not a search. Needs the lead's call.

**`main` cannot currently run the suite honestly.** The auth-context fix (set tenant
context from the verified token before the Session/User lookups) exists only on
`vq-201-tenant-upload`. On `main` no tenant user can log in under `vaultiq_app`. This
must be ported onto this branch as a prerequisite or Gate 3 cannot be evidenced.

**Super-admin RLS defect is unresolved** (17 pre-existing failures). Gate 3 requires a
green suite, which is unreachable until it is fixed. It is a prerequisite, not VQ-202
work.

**Migration numbering.** `main` head is `006_sessions_tenant_nullable`; VQ-201 also adds
a `007` against the same parent. Two children of one revision will need a merge revision
when VQ-201 lands.
