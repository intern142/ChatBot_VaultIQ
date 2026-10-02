"""VQ-302: merge the four Sprint 3 branch heads into one linear history.

Why this file exists
--------------------
Four stories in Sprint 3 were built against `main` at the same time and each
declared its migration directly on top of `006_sessions_tenant_nullable`:

    vq-202 (approval/versioning)     006 -> 007_vq202 -> 008_platform_access
    vq-201/vq-301 (upload + users)   006 -> 007_vq201 -> 008_extraction
                                     -> 009_platform_backport -> 27905f13
                                     -> c4d81f0a7e26
    vq-204 (search index)            006 -> 010_search_index
    vq-305 (feedback)                006 -> 011_feedback

That was fine while each branch stood alone. It is not fine now that VQ-302
needs every one of their tables to exist at the same time: four independent
heads means `alembic upgrade head` has no single target and fails, and a fresh
CI database has no defined order in which to apply them.

This revision exists only to collapse those heads into one. It creates no
tables, no columns, no policies and no indexes, and its upgrade() and
downgrade() are both no-ops on purpose. The value is entirely in
`down_revision`: naming all four heads is what makes Alembic compute a single
linear order for them.

The order Alembic will apply, and why it is the safe one
-------------------------------------------------------
Among the four heads there are two that touch the same objects:

  * `008_platform_access_superadmin` (vq-202) and
    `009_platform_access_backport` (vq-301) are the SAME fix for Known Defect
    #2 - super-admin rows have tenant_id IS NULL, so the bare
    `tenant_id = current_setting(...)` policies could not see them. vq-301
    carries a backport so that branch could be proven green without waiting for
    a merge. Both create a policy named `platform_account_access` on `users`
    and `sessions`.

    PostgreSQL raises `duplicate policy` if you CREATE a policy with a name
    that already exists on that table. Each migration therefore does
    `DROP POLICY IF EXISTS` before its own `CREATE POLICY`, which makes them
    mutually idempotent: whichever runs second drops and recreates the first
    one's policy. The end state is one policy with one definition, and the two
    definitions are equivalent. This is deliberate on both sides, not luck -
    the drop-if-exists is in the shipped code of both branches.

  * `007_vq201` adds `documents.category` and `008_document_text_extraction`
    adds the extraction columns, while `007_vq202` adds
    `documents.document_group_id` / `version_number` / `supersedes_id` /
    `status` / `approved_by` / `approved_at` / `decision_note`. Disjoint
    columns on one table, so either order works; the tree below happens to put
    the VQ-201 pair first.

A note on the numbering: `007` and `008` are each used twice (once by the
vq-202 line, once by the vq-201 line). That is harmless because Alembic
identifies revisions by their `revision` string, not by the filename, and every
`revision` value in the tree is unique. The duplicate prefixes are a readability
wart in `ls alembic/versions` rather than a correctness problem.

What a reviewer should check
----------------------------
This is a structural change and carries no behaviour of its own, so the
evidence that it is correct is not a passing test suite. It is:

  1. `alembic heads` reports exactly one head after this file exists.
  2. `alembic upgrade head` succeeds on a database built from scratch.
  3. The full downgrade to `006` and back up to `head` succeeds, leaving the
     same schema both times.
  4. The full test suite passes on the merged tree, because the platform
     policies really are recreated in the order claimed above.

VQ-202 migration 007 also added the partial unique index
`uq_documents_one_approved_per_group`, which enforces "at most one approved
version per document group". It is a data constraint, not a schema one, so it
survives the round trip and is re-verified by
`tests/test_approval.py::test_exactly_one_approved_at_every_point`.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# The four heads this revision collapses. Order within the tuple is not
# significant - Alembic sorts by dependency - but it is written in the order
# the branches were merged so the file reads top-to-bottom as history.
revision: str = "012_merge_sprint3_heads"
down_revision: Union[str, Sequence[str], None] = (
    "008_platform_access_superadmin",
    "c4d81f0a7e26",
    "010_search_index",
    "011_feedback",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No schema change. See the module docstring."""
    pass


def downgrade() -> None:
    """No schema change, so there is nothing to undo. See the module docstring."""
    pass