# VQ-301 Gate 4 — Self-Review (AC4, password reset)

**Branch:** `vq-301-password-reset`
**Scope:** acceptance criterion 4 only — password reset. This branch does
**not** complete VQ-301.

| Commit | What |
|--------|------|
| `564df83` | Gate 1 approach note — **withdrawn**, wrong actor |
| `7101cde` | Gate 1 corrected: Client Admin issues the code |
| `3399489` | Migration `27905f137fd4` — `reset_codes`, hashed code, two policies |
| `28fe345` | Model, schemas, config, `set_reset_code_context`, router wiring |
| `65c1f35` | `POST /users/{user_id}/password-reset`, `POST /auth/reset-password` |
| `7bfa2af` | Gate 3 — 26 tests |
| `14e45e9` | CI runs as `vaultiq_app`, adds the branch trigger |
| `cc55536` | CI: fixtures truncate as `ADMIN_DATABASE_URL`, not the app role |

CI on `cc55536`, run **36827084819**: green, **189 passed** in 89s. CI has not
yet been run against this gate's new test.

## Gate 1 was wrong and was corrected before code was written

The first note had the **platform operator / Super Admin** issue the reset
code. `Documents\vq301.txt` says "Password reset via a one-time code **the
admin** hands over", inside a story titled "User management for **Client
Admins**". Every other Sprint 3 story names a Client Admin as the actor for
tenant-scoped work (VQ-201, 202, 203, 302, 304), and VQ-106 AC4 explicitly
denies Super Admin document-content operations.

The code written against the withdrawn design was **reverted, not patched**.
Its `POST /auth/forgot-password` was unauthenticated and returned a live reset
code to any caller — a token-disclosure hole. Nothing from it survives in the
tree; verified by `git log` over `app/routes/auth.py` and by grep: the only
unauthenticated reset route in the tree is `/auth/reset-password`, which takes
a code and returns no code.

## Acceptance criteria — walked one by one

The criteria below are the branch's own, from `APPROACH_VQ301.md`.

### 1. A Client Admin can issue a reset code for a user in their own organisation ✅
- `POST /users/{user_id}/password-reset`, `require_roles("client_admin")` on the
  router (`app/routes/users.py:43`), returns 201 with a 43-char base64url code
  and `expires_at`.
- **No tenant filter in the query** (`app/routes/users.py:116`). This is
  deliberate: `get_current_user` has already set `app.current_tenant` from the
  verified token, so RLS restricts the read. A user id from another tenant
  simply is not visible, which is a 404.
- Tests: `test_client_admin_issues_code_for_own_employee`,
  `test_employee_cannot_issue_code` (403), `test_super_admin_cannot_issue_code`
  (403 — VQ-106 AC4).

### 2. The code is one-time and expires ✅
- `used_at` is claimed by one conditional `UPDATE ... WHERE id = :id AND used_at
  IS NULL AND expires_at > now() RETURNING id` (`app/routes/auth.py:328`).
  Read-then-write would let two holders of one valid code both succeed.
- Expiry is `settings.RESET_CODE_EXPIRY_HOURS` (24h) and is enforced in the same
  `WHERE` clause as well as in the pre-check.
- Tests: `test_code_is_single_use`, `test_expired_code_rejected`,
  `test_concurrent_claims_yield_exactly_one_success` (three concurrent consumes
  of one code → `[200, 401, 401]`).

### 3. The user sets a new password and it satisfies the strength rules ✅
- `validate_password_strength` runs **before** the code is consulted
  (`app/routes/auth.py:297`). Two reasons: a weak password cannot be used to
  probe whether a code is real, and a rejected password leaves the code
  unconsumed and still usable.
- Test: `test_weak_password_rejected_and_code_survives`.

### 4. Immediately afterwards the old password fails and the new one works ✅
- Test: `test_valid_code_changes_the_password`,
  `test_old_password_stops_working_and_new_one_works` — asserts the stored hash
  actually changed and that login with the old password 401s while the new one
  succeeds.

### 5. Sessions stop working and any lockout is cleared ✅
- The reset revokes every unrevoked session for that user and clears
  `failed_login_attempts` / `locked_until` (`app/routes/auth.py:352-361`).
  Without the lockout clear the user would receive a valid new password on an
  account that still cannot log in.
- Tests: `test_reset_revokes_existing_sessions` (pre-reset token 401s),
  `test_reset_clears_a_lockout`.

### 6. Unknown / expired / used / malformed codes are indistinguishable ✅
- One rejection helper, `_reject_reset`, returns 401 with the single body
  `RESET_FAILURE_DETAIL` and sleeps out a 200 ms floor
  (`app/routes/auth.py:268-279`). Status, body and elapsed time all match.
- Tests: `test_unknown_and_malformed_codes_are_indistinguishable` (four shapes
  → one status, one body), `test_code_is_single_use` and
  `test_expired_code_rejected` assert the same detail.
- **Added at this gate:** `test_failures_take_at_least_the_floor_time` — the
  floor was implemented but nothing tested it, so a regression that removed the
  sleep would have passed the suite. It now asserts each failure path takes
  ≥200 ms and that the spread between them is under the floor.

### 7. No cross-tenant issue or use, and no self-reset through this path ✅
- Cross-tenant issue → 404, and `reset_codes` is asserted empty afterwards
  (`test_cannot_target_another_tenant`), so it is a refusal and not a write.
- Cross-tenant use: the claim can only write to the `tenant_id` on the row the
  code unlocked, which the caller cannot influence.
  `test_cross_tenant_code_cannot_be_used` proves tenant B's user is untouched
  and that no code row exists for B.
- Self-target refused with 400 and a message pointing at the change-password
  flow (`test_cannot_reset_own_account`) — an admin issuing themselves a code
  they then consume unauthenticated is a way to lock yourself out.

### 8. Both the issuing and the completing action are audited ✅
- `request_password_reset` on issue (`app/routes/users.py:158`) and
  `complete_password_reset` on completion (`app/routes/auth.py:368`).
- Test: `test_both_actions_are_audited` — two `audit_logs` rows with the
  correct actor, target and action.
- **Also tested:** `test_code_value_is_not_audited` asserts the plaintext code
  is not written into `details`. A code in the audit trail would be a durable
  copy of a live credential.

## Must Be Proven

- Issue, consume, expire, single-use, race, session revocation, lockout clear,
  cross-tenant, hashing, audit, uniform failure — all automated.
- Live container evidence — Gate 6, still outstanding.

## Checklist (`.github/CHECKLIST.md`)

### Code Quality
- [x] Project style followed; no `print()` in production code
- [x] No unused imports (`RESET_MIN_ELAPSED` and `time` added for the new test
  and used)
- [x] Functions focused; error handling present on every rejection path

### Database & Migrations
- [x] Reversible — `downgrade()` drops both policies, disables RLS, drops the
      index and the table
- [x] Round trip verified locally: upgrade → downgrade → upgrade, with
      `reset_code_lookup` still SELECT-only after the second upgrade
- [x] `ix_reset_codes_user_live (user_id, used_at, expires_at)` serves the
      per-user cap and the hash lookup
- [x] FK behaviour chosen deliberately: `tenant_id` and `user_id` CASCADE,
      `created_by` SET NULL so deactivating an admin does not destroy a live
      reset path
- [x] Uniqueness at DB level: `code_hash` is UNIQUE

### Security
- [x] Input validation — Pydantic schema on both bodies; an empty code is a 422
      before any lookup
- [x] No SQL injection — ORM queries and bound parameters throughout; the code
      is only ever hashed, never interpolated into SQL
- [x] Authentication where required; the unauthenticated endpoint takes a
      256-bit one-time code as its only credential, by design
- [x] Authorization enforced — `ROLE_MATRIX` entry plus router-level
      `require_roles("client_admin")`
- [x] Sensitive data not logged and not audited — code hashed at rest, absent
      from `details`, never written to a log line
- [x] Config in `app/config.py`, overridable by env; **added at this gate**:
      `RESET_CODE_EXPIRY_HOURS` and `RESET_CODE_MAX_LIVE_PER_USER` were missing
      from `.env.example` and are now documented there

### API Design
- [x] `response_model` on both endpoints
- [x] Status codes consistent: 201 issue, 200 complete, 400 weak password and
      self-target, 403 wrong role, 404 unknown/other-tenant user, 422 schema

### Testing
- [x] 27 tests in `tests/test_password_reset.py`, including the negative paths,
      the RLS policy tests against `vaultiq_app` (`app_db_conn`), and now the
      timing floor
- [x] Full suite green locally: `python -m pytest tests/ -q` → **190 passed**
      (189 before this gate's new timing test, 190 after), 5m03s
- [x] No external service dependencies — no mail relay, no network

### Multi-Tenancy
- [x] `reset_codes.tenant_id` is `NOT NULL` with a FK to `tenants`
- [x] RLS enabled **and** `FORCE`d
- [x] Two policies: `tenant_isolation` (ALL, tenant context) and
      `reset_code_lookup` (**SELECT only**, keyed on the hash the caller
      already holds)
- [x] The consuming endpoint sets tenant context **from the row the code
      unlocked**, never from caller input (`app/routes/auth.py:323`)
- [x] `NULLIF(current_setting(...), '')::uuid` used in both policies — a pooled
      connection between transactions holds the empty string and `''::uuid`
      raises. This is load-bearing, not stylistic.

### Files & Structure
- [x] New files in the right directories
- [x] No new dependencies — no `requirements.txt` change needed
- [x] Config change reflected in `.env.example`

## Deviations from the approach note (declared)

1. **Endpoint mounted at `/users`, not `/admin`.** The note's endpoint table and
   file list were corrected at this gate to match what was built. Reason: the
   `/admin` router is `require_roles("super_admin")` at router level, and
   `test_tenant_lifecycle` asserts every `/admin` operation is Super Admin only
   and that there are exactly six. `/admin` keeps meaning "platform operator";
   a client managing its own staff is a different thing.
2. **Three findings left alone deliberately**, recorded here rather than fixed,
   because each is outside this story:
   - `invites` still stores its codes in plaintext. `reset_codes` does not.
     Changing invite codes alters a shipped flow.
   - **No rate limiting on `/auth/reset-password`.** The 200 ms floor bounds the
     rate at roughly 5/s per connection, and codes are 256-bit so guessing is not
     the attack. Flagging it for the security story; adding a limiter here would
     be scope creep on AC4.
   - Super Admin auth has a pre-existing RLS defect where `users` FORCE RLS
     filters NULL-tenant rows in `get_current_user`. Not introduced here, not
     fixed here.

## Known gaps

- **Gate 6 (live container) not done.** Test output is not proof.
- The other five VQ-301 criteria are not started: invite one user, CSV import
  with validate-all-then-apply-or-none and a row-by-row report, deactivate /
  reactivate, role change Employee↔Client Admin behind step-up re-authentication,
  and tenant-scoped auditing across all of it.
- Migration ordering against VQ-201 / VQ-202 / VQ-203 is unresolved: all four add
  a migration against overlapping parents.