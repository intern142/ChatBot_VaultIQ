# VQ-301 — Gate 4 self-review (AC1, AC2, AC3, AC5, AC6)

Walked one criterion at a time against the code, then against `.github/CHECKLIST.md`.
Every claim below was checked, not assumed. Where the check found something, it is
recorded as a finding rather than quietly fixed — including the three that changed
the design, which are also written up in `APPROACH_VQ301_USERMGMT.md`.

Branch `vq-301-password-reset`. Full suite **279 passed, 0 failed** (190 before this
work; +89 new).

---

## AC1 — A Client Admin can invite one user into their organisation

| # | Criterion | Evidence | Confirmed |
|---|-----------|----------|-----------|
| 1 | An admin can invite a single person by email | `POST /users/invites` → 201, `test_invites_an_employee_and_they_accept_at_that_role` | ✅ |
| 2 | The invited person becomes a user of **that** organisation and no other | `test_invite_binds_to_the_issuing_tenant_only` — the accept call carries no tenant; only `invite.tenant_id` can place the user | ✅ |
| 3 | The invited user gets the role that was asked for, not a fixed one | `invite.role` → `User.role` in `app/routes/invite.py`; `test_invites_an_employee_and_they_accept_at_that_role` logs in and reads `role == "employee"` | ✅ |
| 4 | The invite cannot be used twice, or after it expires | `test_invite_is_one_time`, `test_expired_invite_is_refused` | ✅ |
| 5 | One admin cannot invite into another organisation | `test_email_that_exists_in_another_tenant_is_not_visible`, `test_invite_binds_to_the_issuing_tenant_only` | ✅ |
| 6 | An employee or the platform operator cannot invite | `test_employee_cannot_invite` (403), `test_super_admin_cannot_invite` (403) | ✅ |
| 7 | `super_admin` is not invitable through a client-facing endpoint | 422 at the schema, **and** `ck_invites_role_is_tenant_role` at the database | ✅ |

**Criterion 5 deserves a note.** The obvious test — "A invites an email, get a 409
because B already has it" — is the *wrong* test. It would pass only if B's rows were
visible, and the 409 itself would tell A's admin that the address is in use
somewhere in VaultIQ. The test asserts the opposite: the invite **succeeds**, because
from A's point of view that address is free. `test_invite_binds_to_the_issuing_tenant_only`
then confirms the row landed in A.

---

## AC2 — Import a staff list from CSV, all-or-nothing, with a row-by-row report

| # | Criterion | Evidence | Confirmed |
|---|-----------|----------|-----------|
| 1 | A CSV of `email,role` is accepted and every row becomes a user | `test_imports_a_valid_file` (2 rows, both created) | ✅ |
| 2 | **One bad row → nothing is applied** | `test_one_invalid_row_creates_nothing_at_all`: 3 rows, 1 bad, `created_count == 0`, and `users` count for the two good rows is `0` | ✅ |
| 3 | The report names every row and gives a reason | `test_report_covers_every_row_not_only_the_bad_ones`, `test_report_line_numbers_survive_blank_lines` | ✅ |
| 4 | All-or-nothing is structural, not a rollback that might fail | Nothing is written until every row validates; returning early *is* the guarantee | ✅ |
| 5 | No password is invented or shipped | No password column. Each user gets the hash of a discarded 256-bit value — `test_imported_user_cannot_log_in_until_they_reset` | ✅ |
| 6 | An imported user can actually get in | `test_imported_user_can_log_in_after_a_reset` — AC4 reset, then login | ✅ |
| 7 | The file cannot be used to reach another tenant's users | `test_other_tenants_users_are_not_treated_as_duplicates` — `emp@b.com` imports into A | ✅ |
| 8 | The endpoint is bounded | 501 rows → 400 (`test_the_refusal_is_at_the_boundary`); >1 MB → 400 (`test_oversized_file_is_refused_before_parsing`) | ✅ |
| 9 | Only a Client Admin may import | `test_employee_cannot_import`, `test_super_admin_cannot_import` — both 403 | ✅ |

---

## AC3 — A Client Admin can deactivate and reactivate a member of staff

| # | Criterion | Evidence | Confirmed |
|---|-----------|----------|-----------|
| 1 | Deactivation takes effect on the user's **next** request | Flag and session revocation in one transaction; `test_deactivated_users_existing_token_stops_working` — a token that returned 200 one call earlier now returns 401 | ✅ |
| 2 | They cannot log in again while deactivated | `test_deactivated_user_cannot_log_in` | ✅ |
| 3 | "Deactivated" is indistinguishable from "wrong password" | Same 401, same body, asserted by comparing the two responses directly | ✅ |
| 4 | Reactivation restores login | `test_reactivate_restores_login` | ✅ |
| 5 | Reactivation does not silently restore old sessions | `test_reactivate_does_not_resurrect_sessions` | ✅ |
| 6 | Cross-tenant target is refused | `test_cannot_target_another_tenant`, `test_cannot_reactivate_another_tenant` — both 404, and B's row is asserted unchanged | ✅ |
| 7 | Employee and platform operator refused | 403 each | ✅ |
| 8 | A tenant is never left with nobody who can administer it | `test_a_tenant_is_never_left_without_an_active_admin` | ⚠️ see Finding 2 |
| 9 | Both operations are audited | `test_both_operations_are_audited` | ✅ |

---

## AC5 — Role change, behind step-up re-authentication

| # | Criterion | Evidence | Confirmed |
|---|-----------|----------|-----------|
| 1 | An admin can move a user between employee and client_admin | `test_employee_promoted_to_client_admin`, `test_demotion_is_allowed_when_another_admin_exists` | ✅ |
| 2 | The caller's password is required on **this** request | `current_password` is a required field; `test_missing_current_password_is_refused` (422) | ✅ |
| 3 | A wrong password changes nothing | `test_wrong_current_password_is_refused_and_changes_nothing` — 401 **and** the role is still `employee` in the database | ✅ |
| 4 | The step-up cannot be used to probe for user ids | `test_wrong_password_is_refused_before_the_target_is_looked_up` — 401 for a random UUID and for a real id alike | ✅ |
| 5 | The change takes effect immediately, not at next login | Target sessions revoked; `test_sessions_are_revoked_on_demotion` — a token holding the old privilege stops working | ✅ |
| 6 | The new role is real, not just a database row | `test_promoted_user_actually_gets_the_new_permissions` — old token refused, fresh login can invite | ✅ |
| 7 | `super_admin` is not reachable | 422 at the schema | ✅ |
| 8 | Self-role-change refused | `test_cannot_change_your_own_role` (400) | ✅ |
| 9 | Cross-tenant target is 404 | `test_cannot_target_another_tenant` — and B's role asserted unchanged | ✅ |
| 10 | Employee and platform operator refused | 403 each | ✅ |
| 11 | No credential in the audit row | `test_audit_row_has_no_password` | ✅ |

---

## AC6 — Every user-management action is recorded, visible to that tenant only

| # | Criterion | Evidence | Confirmed |
|---|-----------|----------|-----------|
| 1 | Each of the six operations writes its row | `test_every_operation_leaves_a_row` — asserts the set of six action names is present | ✅ |
| 2 | Actor and role recorded correctly | `create_user_invite`, `deactivate_user`, `reactivate_user`, `change_user_role` carry the caller; `accept_invite` carries `actor_role: "system"` and a null actor, asserted in `test_accepted_invite_is_visible_to_the_tenant` | ✅ |
| 3 | Both sides of a role change recorded | `test_role_change_is_audited_with_both_roles` | ✅ |
| 4 | A tenant sees only its own trail | `test_returns_only_this_tenants_rows` | ✅ |
| 5 | No other tenant's identifier or content in the body | `test_body_contains_no_other_tenant_identifier` — B's tenant id, B's audit email and B's admin email all asserted absent | ✅ |
| 6 | There is no way to ask for another tenant's trail | `test_no_tenant_can_be_named_in_the_request` — no tenant parameter exists; passing one is ignored and returns the caller's own rows | ✅ |
| 7 | **No credential ever reaches the trail** | `test_trail_contains_no_invite_or_reset_code` — both 43-char codes absent; `test_audit_row_holds_no_credential_material` — no `$2b$`, no `unusable:` | ✅ |
| 8 | Employee and platform operator refused | 403 each | ✅ |

---

## Findings

### Finding 1 — 200 with `applied: false` was wrong for a failed import

**Found by:** reviewing the status code against `test_isolation_suite.py`'s existing
convention, then against what a frontend would do with it.
**What was wrong:** the first implementation returned `200` with `applied: false` for a
file containing an invalid row, on the reasoning that the report is the deliverable
and should not sit in an error body.

That reasoning loses to the failure mode. A client that treats 2xx as "the rows
landed" renders a green tick over an empty staff list — silent, and it looks like
success. A client that discards 4xx bodies loses the report — visible, and the
frontend author finds it in a day. Silent-wrong beats visible-broken.

**Fixed:** status is now `400`, with the report in the body and declared via
`responses={400: {"model": ImportResponse}}` so OpenAPI shows the same shape on both.
`applied` stays in the body as a machine-readable flag.

### Finding 2 — the last-active-Client-Admin guard is unreachable

**Found by:** writing a test that could not pass. The test tried to have a tenant's
sole admin deactivate themselves and expected the last-admin refusal; it got the
self-target refusal instead.

Tracing it: only a `client_admin` may call these endpoints, and a `client_admin` may
not target themselves. So any caller is necessarily a *second* active Client Admin,
and the count in the guard can never be zero. The same holds for the identical guard
on demotion in AC5.

**Consequence:** the invariant rests entirely on the self-target rule, and the tests
now assert **the invariant** — a sole admin cannot remove or demote themselves, and
the tenant is still administrable afterwards — rather than pretending to reach a
branch that cannot be entered.

Both guards are kept, and both are now commented in the code as currently
unreachable so they do not read as load-bearing. A reviewer who prefers no dead
code can delete them; the guarantee survives, because the rule that enforces it
stays. Recorded rather than quietly dropped, because a silently-removed guard would
be invisible and a comment saying "unreachable" is checkable.

### Finding 3 — three smaller things, all fixed

| | What | Why it mattered |
|---|---|---|
| a | CSV line numbers were counted on the **filtered** list, so every blank line above an error shifted the report by one | The report is the entire deliverable of AC2. Pointing at the wrong line makes it worse than useless. `test_report_line_numbers_survive_blank_lines` now pins lines 2 and 5 across a file with blank lines between them. |
| b | `await file.read()` with no limit on the CSV upload | One request could ask the app to allocate whatever the client chose to send. Now reads one byte past a 1 MB cap. |
| c | `write_audit_log` was duplicated between `admin.py` and `users.py` | A bad place for a duplicate: `tenant_id` on the row is what RLS scopes the read by. Moved to `app/services/audit.py`; `admin.py` keeps a thin wrapper so VQ-107's four call sites and 21 tests are untouched. |

### Deliberately not done

- **No `GET /users` staff listing.** No criterion asks for one, and it is a
  document-adjacent read that would need its own tenant-isolation tests. Flagged in
  the approach note because Intern4 may need it this sprint — a decision, not a gap.
- **No rate limiting on any of the six endpoints.** The existing gap from AC4's
  Gate 6 finding applies here too and is flagged for the security story rather than
  half-fixed in a user-management story.
- **Invite codes stay plaintext in `invites`.** VQ-107's defect, declared rather
  than fixed; fixing it is a credential-storage migration to a shipped flow.
- **No index on `users.is_active` or `invites.role`.** `invites.role` is never read
  in a `WHERE` clause, and `is_active` is only ever read alongside `tenant_id`, which
  the existing `uq_user_email_per_tenant` index leads with. An index on either would
  be write cost for no query.
- **The 500-row cap is not exercised on the accepted side.** 500 bcrypt hashes is
  minutes of CPU to prove one `>` comparison. The refused side is tested, and proves
  the check runs before any hashing.

---

## `.github/CHECKLIST.md`

**Code Quality** — style matches the surrounding routers. No hardcoded secrets: the
one password literal is `STRONG = "StrongPass1!"` in the test module, matching the
existing `conftest.py` fixture convention. No `print()`. Longest function is the
import handler, split into `_parse_import` + the handler. Unused imports removed
(`Tenant`, `Any`, `verify_password` in tests, `hash_password` in tests). Errors are
handled, including the `IntegrityError` race path.

**Database & Migrations** — reversible; verified **upgrade → downgrade → upgrade**,
with the CHECK constraint present after the final upgrade and absent after the
downgrade. No data loss on downgrade: both columns were added with defaults, and
dropping `is_active` loses only the flag that was false solely for users an admin had
deliberately deactivated. No new foreign keys. **Constraints at DB level, not just
app level:** `is_active NOT NULL`, `role NOT NULL`, and `ck_invites_role_is_tenant_role`
— verified by hand, `super_admin` rejected and `employee` accepted. Indexes: none
added, justified above.

**Security** — Pydantic validation on every body. No string-built SQL; the only raw
SQL is `f"SELECT count(*) FROM {table}"` inside the *test* module, where `table` is a
literal. Authentication on all six; authorization via `require_roles("client_admin")`
at router level plus all six in `ROLE_MATRIX`. Nothing sensitive logged — the audit
trail is the thing that could have leaked, and criterion 7 of AC6 tests it. No new
settings, so `.env.example` is unchanged.

**API Design** — consistent shapes (`UserResponse` everywhere a user is returned).
Status codes consistent with the rest of the API: 201 created, 400 invalid input,
401 wrong credential, 403 wrong role, 404 not found, 422 schema violation.
`response_model` on all six. OpenAPI accurate, including the documented 400 on import.

**Testing** — 89 new tests (77 functions, 3 of them parameterised). Edge cases:
blank lines, BOM, non-UTF-8, missing header columns, empty file, 501 rows, oversized
file, duplicate in file, duplicate against existing, cross-tenant duplicate,
already-active, already-inactive, idempotent reactivate, self-target, unknown id,
locked account. Negative paths throughout — **45 of the 77 functions assert an error
status**, counted rather than estimated. Full suite green locally.

**Multi-Tenancy** — no new tables. No new RLS policies needed: `users` and `invites`
both already carry FORCE RLS and `tenant_isolation`, and a new column is not a new
visibility rule. Every query runs under the context `get_current_user` set from the
verified token. Cross-tenant access blocked on all four id-taking operations (404) and
on the audit read (no tenant parameter exists). Super admin correctly refused on all
six (403). All six added to `tests/isolation_manifest.py` so the VQ-110 coverage
guard accepts them.

**Files & Structure** — new files in `app/routes/`, `app/schemas/`, `app/services/`,
`alembic/versions/`, `tests/`. No `__init__.py` exports needed. No dependency
changes. No new artifact types.

---

## Live container (Gate 6)

Not yet performed for these five criteria. Recorded separately in `AGENTS.md` and on
PR #14 when done — a passing suite is not the evidence, per the SOP.

**Gate 4 status: complete.** Acceptance criteria walked one at a time, three findings
recorded and two of them changed the design.