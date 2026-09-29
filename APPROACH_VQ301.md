# VQ-301 Approach Note — Password Reset Flow

## Objective
Allow any user (Client Admin or Employee) to reset their password when forgotten, without internet/email, using a one-time code produced by the platform operator and handed over on screen.

## Acceptance Criteria (from SOP / AGENTS)
1. **Forgot-password request** — user supplies organisation_code + email; system produces a one-time, time-limited reset code; operator hands it to the user on screen.
2. **Reset with code** — user submits code + new password; password strength enforced; code consumed; user can then log in with new password.
3. **No user enumeration** — wrong org_code, wrong email, wrong code all return identical response + timing.
4. **No internet** — no outbound mail; code shown to operator (Super Admin) via API, operator relays manually.
5. **Audit trail** — every reset request and completion recorded with actor.

## Design

### Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/forgot-password` | none | org_code + email → returns `{ reset_code: "..." }` **only to Super Admin** |
| POST | `/auth/reset-password` | none | code + new_password → consumes code, updates password_hash |

### Code design
- `reset_codes` table: `id, user_id, code (43-char base64url), expires_at, used_at, created_by (super_admin user_id), created_at`
- Super Admin calls `/auth/forgot-password` → system validates org_code+email exist, creates code row, returns code to Super Admin.
- User (unauthenticated) calls `/auth/reset-password` with code + new password → validates code (unused, unexpired, matches user), updates password, marks code used.
- Both endpoints constant-time, uniform error messages.

### Security
- Code length: 32 bytes → 43-char base64url (same as invite codes).
- Expiry: 24 hours (configurable).
- One-time: `used_at` set on successful reset.
- No email sent — Super Admin copies code from response and gives to user.
- Rate limit: max 3 reset requests per user per hour (tracked in `reset_codes`).

### Integration points
- Reuses `hash_password`, `verify_password_strength` from `app.auth.password`.
- Reuses `create_access_token` flow for subsequent login.
- Audit via existing `audit_logs` table (action: `request_password_reset`, `complete_password_reset`).

## Files to touch
- `alembic/versions/xxx_vq301_password_reset.py` — migration (reset_codes table, RLS, grants)
- `app/models/reset_code.py` — SQLAlchemy model
- `app/schemas/auth.py` — `ForgotPasswordRequest`, `ForgotPasswordResponse`, `ResetPasswordRequest`
- `app/routes/auth.py` — two new endpoints
- `app/auth/password.py` — ensure strength validation reused
- `tests/test_auth.py` — add reset flow tests (10+ cases)

## Tests
| Case | Expected |
|------|----------|
| Valid org_code+email → Super Admin gets code | 200, code in body |
| Invalid org_code → same response | 404/400 uniform |
| Invalid email → same response | 404/400 uniform |
| Code + valid new password → password updated, code consumed | 200 |
| Code + weak password → 400, code not consumed | 400 |
| Expired code → 400 | 400 |
| Used code → 400 | 400 |
| Code for different user → 400 (no leak) | 400 |
| Rate limit (4th request in hour) → 429 | 429 |
| Cross-tenant: user A's code used by user B → 400, no leak | 400 |
| After reset, login with new password works | 200 |
| After reset, login with old password fails | 401 |

## Risks
- Timing attacks on org_code/email existence — must use constant-time compare and uniform delay.
- Code exposure in logs — never log the code value.
- Super Admin impersonation — reset endpoint only callable by Super Admin (role check).
- RLS: `reset_codes` is platform-scoped (Super Admin creates, unauthenticated user consumes via code lookup). Two policies needed.

## Gate 1 deliverable
This document, posted for approval before any code.

## Next step
Reviewer approval → Gate 2 implementation on branch `vq-301-password-reset`.