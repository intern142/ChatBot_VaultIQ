# VaultIQ — Current Status

**Branch:** `vq-fe2-login_page`
**Last commit:** `7a28b0e` (FE2-14)
**Date:** 2026-09-16

---

## 1. What was completed

### Login Page Redesign (FE2-12)
- Two-column desktop layout: left branding panel + right login form
- Branding: VaultIQ logo/name, headline *"Find the answer. Trust the source."*, support line *"Your company knowledge, securely at your fingertips."*, three feature badges (Encrypted, Document Management, AI-Powered Search)
- Right panel: existing 5-field form in polished card (Welcome back heading, all fields unchanged)
- New visual enhancements: password show/hide toggle, "Forgot password?" link, loading spinner in button, chip-style User Type selector
- Full responsive: desktop two-column, mobile stacks branding above form
- Monochrome proof-grid design, no external assets, works offline

### Mock Backend & API Layer (FE2-13)
- **Single config switch** (`src/api/config.ts`): `VITE_API_MODE=mock|real` (default `mock`)
- **Shared types & errors** (`src/api/types.ts`): `LoginRequest`, `RegisterRequest`, `LoginResponse`, `RefreshResponse`, `ApiError`
- **Real HTTP driver** (`src/api/real.ts`): fetch wrapper with `Authorization: Bearer` + `X-Refresh-Token` headers from `TokenStore`
- **Mock backend** (`src/api/mock/`):
  - `tokens.ts` — fake JWT-shaped tokens with `jti` counter to avoid collisions in test mode
  - `db.ts` — in-memory orgs/users/sessions with seeded fixtures (ORG-12345, ORG-67890; super-admin, client-admin, employee)
  - `handlers.ts` — endpoint implementations matching the spec:
    - `POST /auth/login` → 401 INVALID_CREDENTIALS for bad creds/wrong org/role mismatch
    - `POST /auth/register` → 409 EMAIL_EXISTS, 403 SUPER_ADMIN_DISABLED
    - `POST /auth/refresh` → rotates tokens, invalidates old refresh token
    - `POST /auth/logout` → revokes session
    - `POST /auth/verify` → validates access token
  - `index.ts` — `mockAuthApi` driver with ~180ms latency (0 in test mode)
- **Common facade** (`src/api/auth.ts`): exports `authApi` that delegates to mock or real driver based on config
- **Tests runnable against both backends** (default mock; `VITE_API_MODE=real` points at real):
  - `src/api/__tests__/mockApi.test.jsx` — 13 tests: endpoint contract, error codes, session lifecycle
  - `src/api/__tests__/authFlow.test.jsx` — 9 tests: AuthContext + Login flows (success, wrong creds, lockout, register, empty fields)
- **Config docs**: `frontend/.env.example` + `.gitignore` for `.env*`

### Radio Alignment Fix (FE2-14)
- Added `.role-radio-group` / `.role-radio` CSS for inline radio + label alignment
- Flexbox centering (`align-items: center`, `gap: 0.45rem`) — checkbox and text now on single line
- Grid layout (3 columns), hover/active/checked states match design

### Role-Based Redirects
- Employee → `/employee/dashboard`
- Client Admin → `/admin/dashboard`
- Super Admin → `/super/dashboard` (changed from `/super/tenants`)

---

## 2. What remains

- Real backend implementation (out of scope — this is the mock)
- Integration test against a running real backend (requires deployed backend + `VITE_API_MODE=real`)
- Register page styling regression (uses `.login-card` which was restyled for split layout; currently left-aligned on desktop)
- Consider removing `failedAttempts` from `login`/`register` deps in `AuthContext` (pre-existing lint warning)

---

## 3. Files changed

### New files
| File | Purpose |
|------|---------|
| `src/api/types.ts` | Shared request/response types + `ApiError` |
| `src/api/config.ts` | `VITE_API_MODE` / `VITE_API_BASE` switch |
| `src/api/real.ts` | Real HTTP driver with token binding |
| `src/api/mock/tokens.ts` | Fake JWT token creation/validation |
| `src/api/mock/db.ts` | In-memory org/user/session store with fixtures |
| `src/api/mock/handlers.ts` | Endpoint implementations + error responses |
| `src/api/mock/index.ts` | Mock driver with latency |
| `src/api/__tests__/mockApi.test.jsx` | Endpoint contract tests |
| `src/api/__tests__/authFlow.test.jsx` | AuthContext + Login UI flow tests |
| `frontend/.env.example` | Documented config variables |
| `docs/CURRENT_STATUS.md` | This file |

### Modified files
| File | Changes |
|------|---------|
| `src/api/auth.ts` | Rewired as facade; re-exports types + config |
| `src/pages/Login.jsx` | Uses AuthContext `error` + local `localError` for empty fields |
| `src/components/Icons.jsx` | Added `EyeIcon` / `EyeOffIcon` for password toggle |
| `src/App.jsx` | Super Admin default redirect → `/super/dashboard` |
| `src/index.css` | Added `.role-radio-group` / `.role-radio` styles (FE2-14) |
| `frontend/.gitignore` | Added `.env` / `.env.*` (keep `.env.example`) |

---

## 4. Bugs discovered

| Issue | Location | Status |
|-------|----------|--------|
| Login form didn't display API errors (only local validation) | `Login.jsx` | Fixed — now uses AuthContext `error` + local `localError` |
| Mock token collision in test mode (same ms = same token) | `mock/tokens.ts` | Fixed — added `jti` counter |
| Register page layout regression after split-layout restyle | `Register.jsx` + `index.css` | Known — `.login-card` now left-aligned; needs separate fix |
| AuthContext `refreshAccessToken` missing dep / closure issues | `AuthContext.jsx` | Pre-existing lint warnings |
| `verify()` / `refresh()` / `logout()` sent no auth headers | `auth.ts` (old) | Fixed — real driver now binds tokens from `TokenStore` |

---

## 5. Decisions made

- **Mock defaults to `mock`** — works offline, zero-config for dev & CI
- **Mock implements sane backend policies** — rejects super-admin self-signup, validates role↔userType match
- **Error contract unified** — both mock and real throw `ApiError(status, message, code)`; message embeds status so `err.message.includes('401')` checks in AuthContext work unchanged
- **Tests target the active driver** — no mocking of `../api/auth`; same test file runs against mock (default) or real (`VITE_API_MODE=real`)
- **Token rotation on refresh** — old refresh token revoked, new pair issued (matching real IdP behavior)
- **No external dependencies** — all inline, works with cable pulled

---

## 6. Next recommended steps

1. **Fix Register page layout** — add a dedicated `.register-page` / `.auth-card` style block that centers the card like the old design, or extend the split layout to a register-brand panel
2. **Run against real backend** — deploy backend, set `VITE_API_MODE=real`, `VITE_API_BASE=/api`, run `npm test` to validate same test suite passes
3. **Add E2E test** (Playwright) that exercises login→dashboard→logout against both backends
4. **Consider extracting `setError` to AuthContext** for cleaner empty-field handling in Login
5. **Address AuthContext lint warnings** (stale closures, missing deps) in a dedicated refactor