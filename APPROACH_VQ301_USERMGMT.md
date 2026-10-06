# VQ-301 — Gate 1 approach note for the remaining five criteria

Supersedes nothing. `APPROACH_VQ301.md` remains correct for AC4 (password reset),
which is built, tested and Gate 6 verified. This note covers **AC1, AC2, AC3, AC5,
AC6** — the five that were left unstarted.

Branch: `vq-301-password-reset`, continued. Not a new branch, because a new branch
would add a sixth migration against the same unresolved parent ordering.

## The actor is the Client Admin, in their own tenant

Established for AC4 and unchanged here. Every endpoint below is `client_admin`
only, mounted under `/users`, never under `/admin`. `test_tenant_lifecycle.py`
asserts every `/admin` operation is Super Admin only and that there are exactly
six of them; this story adds six more tenant-scoped operations and none of them
may appear under `/admin`.

## AC1 — invite one user

`POST /users/invites` (Client Admin) issues a one-time, time-limited invite for
one email, role `employee` or `client_admin`, in the caller's own tenant.
`POST /invite/accept` — the existing public endpoint — creates the user at the
role the invite carries.

### Reuse the `invites` table rather than adding `user_invites`

Decision: add a `role` column to `invites` and use that table.

Rejected: a second table for the same concept. It would mean a second code-lookup
RLS policy, a second accept path or a flag on the first, and two tables that both
hold "a code that creates a user". Reviewable code should not have two of those.

### The accept endpoint stops hardcoding `client_admin`

`app/routes/invite.py` currently hardcodes `role="client_admin"` and refuses
accept if the tenant already has one. Both change:

- the created user's role comes from `invite.role`;
- the "tenant already has a Client Admin" refusal applies **only** when
  `invite.role == "client_admin"`, preserving VQ-107 AC3 exactly for the
  bootstrap case it was written for.

`invite.role` defaults to `client_admin` so every existing row keeps its
current meaning without a data backfill.

### Codes stay plaintext in `invites` — declared deviation

This creates new credentials in a table that stores its codes in plaintext.
That is VQ-107's known defect, raised at Gate 4 of AC4 and not fixed there.

Declaring it rather than fixing it, because fixing it means hashing the column,
changing the `app.invite_accept_code` RLS policy to key on a digest, rewriting
`/invite/accept`, and updating the VQ-107 RLS tests that assert on that policy —
all of which is a credential-storage migration to a shipped flow, in a story about
user management. A reviewer may reasonably overrule this; it is a deliberate
choice with a cost, not an oversight.

`reset_codes` (AC4) does hash. That asymmetry is intentional and temporary.

## AC2 — CSV import, all-or-nothing, row-by-row report

`POST /users/import` (multipart CSV, Client Admin).

Header row required. Columns: `email`, `role`.

**Validate everything, then apply.** Every row is parsed and checked first. If any
row is invalid the response is `400` with a per-row report and **nothing is
written** — no partial import, because half a staff list is worse than none and the
admin cannot tell which half landed.

Reported per row: line number, email as given, and either `created` or `invalid`
plus a reason. Reasons: malformed email, role not in {employee, client_admin},
duplicate email within the file, duplicate within the file's own tenant.

### 400, not 200 with `applied: false`

Corrected during Gate 2. The first implementation returned `200` with
`applied: false` and the report, on the reasoning that the report is the
deliverable so it should not sit in an error body.

That is wrong for this API. Every other validation failure here is a 4xx, and a
client that treats 2xx as "the rows landed" renders a green tick over an empty
staff list. That failure is silent and looks like success. A client that discards
4xx bodies loses the report, which is a visible bug the frontend author notices in
a day.

Silent-wrong beats visible-broken. So the status is `400`, the report is in the
400 body with the same `ImportResponse` shape (declared via
`responses={400: {"model": ImportResponse}}`), and `applied` stays in the body as a
redundant machine-readable flag.

Row cap of 500 per request, refused before any parsing and before any bcrypt work.
An unbounded import is a way to fill the `users` table in one call.

### No passwords in the CSV

The file has no password column. Each created user gets a random unusable
password and must set their own through the AC4 reset flow.

Rejected: a shared or per-row password in the file. A CSV sits in someone's
Downloads folder and in mail attachments; it would be a plaintext credential store
we invented. Reusing AC4 means no new credential path and no new secret to lose.

## AC3 — deactivate and reactivate

Migration adds `users.is_active BOOLEAN NOT NULL DEFAULT true`, so every existing
row is active and the downgrade is a drop, not a data restore.

- `POST /users/{id}/deactivate` — sets `is_active = false` and revokes every
  session for that user **in the same transaction**. A deactivated user must be out
  on their very next request, the same semantics VQ-107 AC2 gave tenant suspend.
- `POST /users/{id}/reactivate` — sets it back to true. Does not resurrect
  sessions; they log in again.

### Three refusals, each deliberate

1. **Cannot deactivate yourself.** Same argument as AC4's self-reset refusal: an
   admin can lock themselves out of an account nobody else may manage.
2. **Cannot deactivate the tenant's last active Client Admin.** Otherwise the
   tenant has nobody who can invite, import, reactivate or reset anyone, and is
   permanently unadministrable through the product.
3. **Cross-tenant target is 404, not 403.** VQ-103's rule; the read is not
   tenant-filtered because `get_current_user` already set the context.

### Finding from Gate 2: refusal 2 is unreachable, and 1 is what holds

Written up here rather than left for the reviewer to discover, because it changes
how refusal 2 has to be tested and an unexplained dead branch invites the question
"did you test this?"

Only a `client_admin` may call these endpoints, and refusal 1 means a client_admin
may not target themselves. So any caller is necessarily a *second* active Client
Admin, and the count in the guard is never zero. The same holds for the identical
guard on demotion in AC5.

The last-admin guarantee therefore rests on the self-target rule, and the tests
assert **the invariant** — that a sole admin cannot remove or demote themselves,
and the tenant is still administrable afterwards — rather than pretending to reach
the guard.

Both guards are kept as defence-in-depth for the day either rule above is relaxed,
and both are commented in the code as currently unreachable so they do not read as
load-bearing. A reviewer who prefers no dead code can have them deleted; the
invariant survives, because the rule that actually enforces it is still there.

The alternative — dropping refusal 1 and letting refusal 2 carry the guarantee —
was rejected. Self-demotion is a legitimate action that the product should support
if it is to support an admin leaving, and it is much better served by a dedicated
flow than by a client admin demoting themselves over PATCH.

### Inactive users fail identically to wrong passwords

Login returns the same `401 {"detail":"Invalid credentials"}` for a deactivated
account as for a bad password, on the same ~200ms floor. "Your account is
deactivated" would confirm the address is registered.

`get_current_user` also checks `is_active`. Sessions are revoked on deactivate so
this is defence in depth — a session restored from a backup would still be refused.

## AC5 — role change behind step-up re-authentication

`PATCH /users/{id}/role`, body `{"role": ..., "current_password": ...}`.

**Step-up means the admin re-enters their own password on this request.** The
`current_password` is verified against the caller's own stored hash with bcrypt.

Rejected: a "recently authenticated within N minutes" flag. It needs a new column
or a claims change, and it is weaker — a token validated 9 minutes ago re-authorises
a privilege change. Re-entering the password per request is stateless and the
stronger of the two.

Constraints:
- Only `employee` ↔ `client_admin`. **`super_admin` is refused** — platform
  accounts are not tenant-scoped work, and VQ-106 reserves them for the operator.
- Cannot change your own role.
- Cross-tenant target is 404.

`/auth/login` reads the role from the database on every login, so a changed role
takes effect at the next login without any token change. A token minted before the
change keeps its old claim until it expires; that is why role change also revokes
the target's sessions, so the change takes effect on their next request too.

## AC6 — tenant-scoped auditing

Every operation above writes an `audit_logs` row through the existing
`write_audit_log` helper: `create_user_invite`, `import_users`,
`deactivate_user`, `reactivate_user`, `change_user_role`, alongside AC4's
`request_password_reset` and `complete_password_reset`.

New `GET /users/audit` (Client Admin) returns their **own** tenant's trail.

No tenant id in the path. The tenant comes from the verified token, so a Client
Admin asking for another tenant's audit gets their own rows — there is no URL to
get wrong. RLS scopes the read the same way it scopes every other tenant table.

**Deliberately not adding `GET /users` (list staff).** No criterion asks for it.
Noted because "user management" without a list is awkward for the frontend, and
Intern4 may need it this sprint — raising it here so it is a decision rather than
a gap. If the reviewer wants it, it is one endpoint and one test.

## Endpoints, all additions

| Method | Path | Role |
|--------|------|------|
| POST | `/users/invites` | client_admin |
| POST | `/users/import` | client_admin |
| POST | `/users/{id}/deactivate` | client_admin |
| POST | `/users/{id}/reactivate` | client_admin |
| PATCH | `/users/{id}/role` | client_admin |
| GET | `/users/audit` | client_admin |
| — | `/invite/accept` | public (existing, modified) |

Route ordering: `/users/audit` is declared **before** `/users/{user_id}/...` so the
literal path cannot be captured as a UUID. FastAPI matches in declaration order and
`{user_id}` is typed `UUID`, so the reverse order would 422 instead of matching.

## Migration

One migration, `down_revision = '27905f137fd4'`:

- `users.is_active BOOLEAN NOT NULL DEFAULT true`
- `invites.role VARCHAR(50) NOT NULL DEFAULT 'client_admin'` — text, not the
  `user_role` enum, for the same reason `audit_logs.actor_role` is text: the enum
  would have to admit values the system does not use, and adding a value to a live
  Postgres enum cannot run inside a transaction.

`is_active` is a boolean, not a status enum. A user is active or not; "pending
invite" is an `invites` row, not a user state.

Reversible: drop both columns. No data loss — both were added with defaults, and
dropping `is_active` loses only the flag, which was false only for users the admin
had deliberately deactivated.

## Tests

New file `tests/test_user_management.py`.

**AC1** invite an employee and accept → user exists at that role; invite for
`client_admin` when one exists → still refused (VQ-107 AC3 intact); invite for an
unknown email / bad role → 422; cross-tenant invite refused; employee cannot
invite; invite cannot be reused or used after expiry; accept binds only to its own
tenant's user.

**AC2** all-valid file → every user created; **one bad row → 400, report lists that
row, and `users` count is unchanged**; duplicate within the file; duplicate against
an existing user; malformed email; bad role; missing header; over-cap file; a file
whose rows are all valid but which would collide with another tenant's user (must
not touch it); every created user gets an unusable password.

**AC3** deactivate → `is_active` false **and every session revoked in the same
transaction**; deactivated user's pre-deactivate token 401; login refused and
byte-identical to a wrong password; reactivate → login works; reactivate does
*not* resurrect sessions; self-deactivate 400; **sole admin cannot remove or
demote themselves and is still administrable afterwards** (the invariant, per the
finding above); cross-tenant deactivate and reactivate both 404; employee 403;
super admin 403; reactivation does **not** clear a lockout.

**AC5** change role with correct `current_password` → applied and target's sessions
revoked, and the promoted user can actually do admin things after re-login;
wrong password → 401 and **role unchanged**; missing password → 422; to
`super_admin` → 422; self → 400; cross-tenant → 404; employee → 403;
wrong step-up password is 401 whether or not the target user id exists, so the
endpoint cannot be used to probe for ids.

**AC6** each of the six operations writes its row with the right actor and target;
**zero rows contain a plaintext code**; `GET /users/audit` returns only the
caller's tenant's rows; cross-tenant audit attempt returns the caller's own rows,
never the other tenant's.

**RLS, as `vaultiq_app`:** with G6ALPHA context, a G6BRAVO user id is a 404; a
G6ALPHA admin cannot insert a user into G6BRAVO.

Full suite must stay green.

## Risks

- **The invite-reuse change touches VQ-107's path.** `test_tenant_lifecycle.py`
  has 21 tests over invite accept and must stay green unchanged. If it does not,
  the change is wrong, not the test. *(Result: green unchanged.)*
- **`is_active` on `users` is a read on the login hot path.** One indexed boolean
  column. Not measured; the VQ-102 AC6 10% latency budget already has no baseline.
- **Role change revokes sessions.** Surprising to an admin who did not ask for it.
  It is what makes the change take effect immediately rather than at next login.
- **Step-up needs the admin's real password typed again.** Annoying by design.
- **The 500-row cap is not exercised on the accepted side.** 500 bcrypt hashes is
  minutes of CPU to prove a single `>` comparison. The refused side is tested and
  proves the check runs before any hashing.
- **Three findings from Gate 2, all corrected in the note above:** the 400 vs 200
  status for a failed import; the unreachable last-admin guards; and keeping the
  server defaults on both new columns rather than dropping them, which is both
  safer for a partially-applied deploy and required by the raw-SQL test fixtures.