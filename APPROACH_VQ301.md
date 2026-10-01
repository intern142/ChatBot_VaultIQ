# VQ-301 — Password reset (Client Admin hands over a one-time code)

> **Gate 1 correction, 30 Sep 2026.** The first version of this note
> (`564df83`) had the **platform operator / Super Admin** issue the reset code.
> That is wrong and it is withdrawn. `Documents\vq301.txt` states the actor as
> "Password reset via a one-time code **the admin** hands over", inside a story
> titled "User management for **Client Admins**". Every other Sprint 3 story
> names a Client Admin as the actor for tenant-scoped work (VQ-201, VQ-202,
> VQ-203, VQ-302, VQ-304), and VQ-106 AC4 explicitly denies Super Admin
> document-content operations. The code written against the withdrawn design
> was reverted rather than patched. Nothing from it survives in the tree.

## Objective

A Client Admin resets the password of one of their own organisation's users.
The system produces a one-time, time-limited code which the admin hands over in
person or on a call. The user then sets a new password themselves, without
internet and without an email address ever being used.

## Scope of this branch

This branch delivers **AC4 only** (password reset), which is what the branch
name says. The other five acceptance criteria of VQ-301 — invite one user, CSV
import with all-or-nothing validation, deactivate/reactivate, role change behind
a step-up re-authentication, and tenant-scoped auditing across all of it — are
**not started**. They are recorded in `AGENTS.md` as remaining VQ-301 work.

## Acceptance criteria for this branch

1. A Client Admin can issue a reset code for a user in their own organisation.
2. The code is one-time and expires; a consumed or expired code cannot be reused.
3. The user sets a new password with the code, and the new password satisfies the
   existing strength rules.
4. Immediately afterwards the old password fails and the new one works.
5. All existing sessions for that user stop working, and any account lockout is
   cleared so the new password can actually be used.
6. Unknown, expired, already-used and malformed codes are indistinguishable to
   the caller — same status, same body, comparable time.
7. A Client Admin cannot issue or use a code for a user in another tenant, and
   cannot reset their own account through this path.
8. Both the issuing and the completing action are written to the audit trail.

## Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/users/{user_id}/password-reset` | Client Admin | Issue a one-time code; returns the code for on-screen hand-off |
| POST | `/auth/reset-password` | none | Consume a code and set a new password |

> **Correction, 1 Oct 2026.** This table originally read
> `/admin/users/{user_id}/password-reset`. The endpoint was built at
> `/users/{user_id}/password-reset` instead, and the note was wrong.
> `app/routes/admin.py` carries `require_roles("super_admin")` at router level,
> so a Client Admin endpoint cannot live there at all. More to the point,
> `test_tenant_lifecycle.py` asserts that every `/admin` operation in
> `ROLE_MATRIX` is Super Admin only and that there are exactly six of them; a
> tenant-scoped operation under `/admin` would have meant weakening that test or
> deleting the invariant. `/admin` keeps meaning "platform operator". Nothing
> else in the design changed.

`/auth/forgot-password` from the withdrawn design is **not** built. An
unauthenticated endpoint that returns a live password-reset code to its caller
is a token-disclosure hole, and it has no place in this design.

## Why the admin endpoint is authenticated and the reset endpoint is not

The admin already holds a valid session and is authorised inside their own
tenant, so a miss there is an ordinary authorisation outcome, answered 404 so
that another tenant's user is not confirmed to exist. The reset endpoint has no
session at all — that is the point of a reset — so every failure mode must look
identical, and the only credential presented is the 256-bit code.

## Code design

- 32 bytes from `secrets.token_bytes`, base64url encoded → 43 characters.
- **Stored as a SHA-256 hash, never in plaintext.** A reset code is a bearer
  credential; a database read must not yield a usable one. (The existing
  `invites` table stores its codes in plaintext, which is a separate finding and
  is not changed here.)
- Expiry: 24 hours, from `settings.RESET_CODE_EXPIRY_HOURS`.
- One-time: `used_at` is set when the code is claimed.
- Cap of 3 live codes per user; issuing a fourth revokes the oldest so a lost
  code cannot permanently block a reset.

## Claiming a code atomically

Reading then writing is a race: two requests with the same valid code could both
read it as unused. The claim is therefore a single conditional statement

    UPDATE reset_codes SET used_at = now()
     WHERE id = :id AND used_at IS NULL AND expires_at > now()
    RETURNING id

If it returns no row, another request won the race and the caller gets the same
uniform failure as a code that never existed.

## How the reset endpoint establishes tenant context

This is the part that is easy to get wrong, and the withdrawn attempt got it
wrong. A public caller has no tenant context, so an ORM read of the `users`
table returns nothing and the request dies with a 401 that looks like a bug.

The `reset_codes` row therefore carries its own `tenant_id`, written when the
Client Admin issues the code. The endpoint reads the single row through a
SELECT-only policy keyed on the exact code hash, takes `tenant_id` from it, and
only then sets the tenant context for the update. The context is therefore
derived from a row that the code itself unlocked, never from caller input.

A `SECURITY DEFINER` claim function was considered and rejected: it widens what
a database identity can do, which is the same trade the VQ-203 worker design
declined for a scheduling problem.

## RLS

`reset_codes` has FORCE ROW LEVEL SECURITY and two permissive policies.

- `tenant_isolation` — `tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid`.
  Governs the Client Admin's management of their own tenant's codes.
- `reset_code_lookup` — `FOR SELECT` only, keyed on
  `code_hash = current_setting('app.reset_code_hash', true)`. This is the
  public, unauthenticated path, and it grants nothing but the ability to find
  the one row whose hash the caller already possesses.

`NULLIF` rather than a bare `current_setting(...)` is required, not stylistic:
a context that was set and then committed reverts to the empty string, and
`''::uuid` raises rather than matching nothing. This is Known Defect 3.

## Files

- `alembic/versions/<rev>_vq_301_password_reset.py` — one migration: table,
  `tenant_id`, RLS policies, grants
- `app/models/reset_code.py` — model
- `app/schemas/auth.py` — `ResetPasswordRequest`
- `app/schemas/user.py` — `PasswordResetIssued`
- `app/routes/users.py` — `POST /users/{user_id}/password-reset` (its own router,
  `client_admin` only; deliberately not under `/admin`)
- `app/routes/auth.py` — `POST /auth/reset-password`
- `app/database.py` — `set_reset_code_context`
- `app/auth/permissions.py` — matrix entries
- `tests/test_password_reset.py` — new file, not appended to `test_auth.py`

## Tests

| Case | Expected |
|------|----------|
| Client Admin issues a code for their own employee | 201, 43-char code |
| Employee is refused the issue endpoint | 403 |
| Client Admin targets a user in another tenant | 404, no code issued |
| Code + valid new password | 200, old password then fails, new one works |
| Code + weak password | 400, code **not** consumed |
| Unknown code / malformed code / expired code / used code | identical 401 body |
| Two concurrent claims on one code | exactly one 200 |
| Reset revokes that user's existing sessions | old token now 401 |
| Reset clears a lockout | new password can log in |
| Admin cannot reset their own account via this path | 400 |
| Code is not stored in plaintext | stored value is a 64-char hex SHA-256 |
| Both actions audited | two `audit_logs` rows with correct actors |
| Cross-tenant: tenant B cannot use tenant A's code | 401, tenant A user unchanged |

## Risks

- A code in a response body can end up in logs. The code is never written to a
  log line, and it is hashed at rest.
- Revoking sessions on reset will sign the user out everywhere. That is the
  intent of a reset and is called out in the response message.
- The public endpoint is a password-setter reachable by anyone holding a code.
  Its only defence is code entropy, expiry and one-time use, all of which are
  tested.
