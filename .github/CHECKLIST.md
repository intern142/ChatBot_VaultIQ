# VQ-105 Review Checklist

## Common Mistakes

- [x] **Identical error messages** — All login failures return `"Invalid credentials"` (wrong email, wrong password, locked account). No user enumeration.
- [x] **Timing attack prevention** — 200ms constant delay on all login outcomes (success and failure).
- [x] **No secrets in code** — JWT_SECRET loaded from env via pydantic-settings, not hardcoded.
- [x] **NoSQL injection** — Parameterized queries via SQLAlchemy ORM.
- [x] **Token expiration** — JWT tokens expire after 24h (configurable).
- [x] **Session revocation** — Logout invalidates session in DB, subsequent requests rejected.
- [x] **Account lockout** — 5 failed attempts → 15 min lockout, successful login resets counter.
- [x] **Super admin isolation** — Super admin (organisation_code=SUPER) skips tenant lookup, no tenant_id in token.
- [x] **Password strength** — Min 8 chars, uppercase, lowercase, digit, special character enforced.
- [x] **RLS enabled** — Row-level security on users table, tenant_id policy active.
