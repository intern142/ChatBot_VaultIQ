# VQ-107 Gate 4 — Self-Review

**Branch:** `vq-107-tenant-lifecycle`
**Commits:** `1b5971a` (Gate 2), `c97c0c2` (Gate 3, 65 tests green)

## Acceptance Criteria — walked one by one

### 1. Create a tenant with code, name and storage quota ✅
- `POST /admin/tenants` (super_admin only) accepts `short_code`, `name`, `storage_quota_mb`
- Short code uppercased, format validated (2-20 uppercase A-Z0-9) → invalid = 422
- Duplicate short code → 409 (IntegrityError handled, not a 500)
- Test: `test_create_tenant_and_audit_log`, `test_create_tenant_duplicate_code_conflict`, `test_create_tenant_rejects_bad_short_code`

### 2. Suspend stops all sessions immediately + logins refused; reactivate reverses it ✅
- `PATCH /admin/tenants/{id}/suspend` sets status=suspended and deletes ALL sessions of the tenant
- A token minted before suspension is refused on the very next request (401) — proven in `test_suspend_blocks_login_and_revokes_sessions`
- Fresh login while suspended → 403 (login endpoint tenant-status check)
- `PATCH .../reactivate` restores status=active; login works again (`test_reactivate_restores_login`)
- State machine guards: double-suspend 400, reactivate-active 400, unknown tenant 404

### 3. Invite the first Client Admin — one-time, time-limited, handed over on screen ✅
- `POST /admin/tenants/{id}/invite` returns a 43-char base64url code (`secrets.token_bytes(32)`), default 7-day expiry
- Mail relay optional: no network/mail configured → code returned in the response for on-screen handover
- Reuse blocked: `used_at` set on accept, second accept → 400 (`test_invite_cannot_be_reused`)
- Expiry enforced: expired invite → 400 (`test_invite_expired_is_rejected`)
- No further invites once the tenant has a client_admin (`test_no_further_invites_after_client_admin_exists`)

### 4. Accepting the invite sets a password and becomes that tenant's Client Admin ✅
- Public `POST /invite/accept` (no auth) — password strength enforced
- Creates user `role=client_admin` bound to the invite's tenant; can log in with `organisation_code` of that tenant
- Test: `test_invite_accept_creates_client_admin` (role + tenant_id asserted from login response)
- Suspended tenant: invite accept refused (`test_invite_accept_for_suspended_tenant`)

### 5. Every action recorded in the audit trail with who did it ✅
- `write_audit_log` called on create/suspend/reactivate/invite (actor = super_admin user) and on accept (actor_role='system')
- `GET /admin/tenants/{id}/audit` returns the trail; `test_audit_records_lifecycle_actions` asserts all five actions present
- actor_role stored as free text (migration 005) because 'system' is not a valid user_role enum value

## Must Be Proven

- **Invite cannot be reused or used after expiry** — ✅ automated tests
- **Suspend takes effect within one request** — ✅ pre-suspend token → 401 on next call
- **Tenant code uniqueness and format** — ✅ 409 on duplicate, 422 on bad format
- **Live container full sequence** — Gate 6 (separate evidence)

## Checklist (from `.github/CHECKLIST.md`)

### Security / Multi-tenancy
- [x] New tables (`invites`, `audit_logs`) have `tenant_id`
- [x] RLS policies applied + FORCE RLS on `invites`, `audit_logs`
- [x] Invite code lookup is a SELECT-only RLS policy keyed on the exact unguessable code — no tenant leak, no write bypass
- [x] Writes require tenant context (`set_tenant_context`) — insert without context blocked (RLS test)
- [x] Admin endpoints super_admin only — denied-role API test + ROLE_MATRIX
- [x] No SQL injection: invitation lookup uses bound params; invite code never interpolated into SQL

### Database & Migrations
- [x] Migration 005 reversible (downgrade present)
- [x] Indexes on `invites(tenant_id, code)`, `audit_logs(tenant_id, actor_user_id, target)`
- [x] FK ON DELETE CASCADE on tenant-scoped FKs
- [x] Uniqueness enforced at DB level (unique invite code, unique tenant short_code, user email per tenant)

### API Design
- [x] Pydantic schemas + validation on all request bodies
- [x] Consistent status codes (201 create, 409 duplicate, 400 state violations, 404 unknown tenant, 403 permission, 422 validation)
- [x] `response_model` on all endpoints

### Testing
- [x] 21 new tests incl. negative paths
- [x] Full suite green: **65 passed** (`pytest -q`)
- [x] No external service dependencies (mail relay optional, not exercised)

## Deviations from Approach Note (declared)
- Invite accept endpoint mounted at `POST /invite/accept` (dedicated `app/routes/invite.py`) exactly as the approach note specified — moved out of the `/auth` prefix where it was originally drafted.
- `audit_logs.actor_role` became VARCHAR(50) (not the `user_role` enum) because accept_invite legitimately records a `system` actor.
- Invite code lookup needs RLS access without tenant context (the bootstrap case). Solved with a SELECT-only policy keyed on `app.invite_accept_code`, documented in migration 005.