# VQ-107 Approach Note — Tenant Lifecycle: Create, Suspend, Reactivate, Invite First Admin

## Objective
Platform operator (Super Admin) can manage tenant lifecycle without touching database directly. No internet/email required — invite codes are displayed on screen.

## Database Changes (Migration 004)

### 1. Add `storage_quota_mb` to `tenants` table
- Integer, nullable (optional quota enforcement later)

### 2. New table: `invites`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, gen_random_uuid() |
| tenant_id | UUID | FK tenants(id) ON DELETE CASCADE, NOT NULL |
| email | VARCHAR(255) | NOT NULL |
| code | VARCHAR(64) | UNIQUE, NOT NULL (cryptographically random) |
| expires_at | TIMESTAMPTZ | NOT NULL |
| used_at | TIMESTAMPTZ | NULLABLE |
| created_by | UUID | FK users(id), NOT NULL (super_admin who created it) |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |

### 3. New table: `audit_logs`
| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, gen_random_uuid() |
| actor_user_id | UUID | FK users(id), NULLABLE (system actions) |
| actor_role | user_role | NOT NULL |
| action | VARCHAR(100) | NOT NULL (e.g., create_tenant, suspend_tenant, create_invite, accept_invite) |
| target_type | VARCHAR(50) | NOT NULL (tenant, invite, user, session) |
| target_id | UUID | NOT NULL |
| details | JSONB | NOT NULL DEFAULT '{}' |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |

### 4. RLS on new tables
- `invites`: FORCE RLS, policy `tenant_id = current_setting('app.current_tenant', true)::uuid`
- `audit_logs`: FORCE RLS, policy `tenant_id = current_setting('app.current_tenant', true)::uuid` — but wait, audit_logs may not have tenant_id directly. Since super_admin creates them and they're tenant-scoped, we'll add tenant_id column to audit_logs.

Actually, for audit_logs, the super_admin needs to write audit entries for any tenant. The vaultiq_app role won't write audit logs directly. The super_admin writes audit logs via the admin endpoints. So we can either:
a) Not put RLS on audit_logs (super_admin writes via admin API)
b) Put RLS with tenant_id, and have admin API set tenant context

Option (b) is better for consistency. Add `tenant_id` to audit_logs.

## Endpoints

### Admin Router (prefix `/admin`, super_admin only)
All require `require_roles("super_admin")` via `ROLE_MATRIX`.

| Method | Path | Description |
|--------|------|-------------|
| POST | /admin/tenants | Create tenant (short_code, name, storage_quota_mb) |
| GET | /admin/tenants | List all tenants (super_admin sees all, no RLS filter) |
| PATCH | /admin/tenants/{id}/suspend | Suspend tenant: status=suspended, revoke ALL sessions |
| PATCH | /admin/tenants/{id}/reactivate | Reactivate tenant: status=active |
| POST | /admin/tenants/{id}/invite | Create invite for first Client Admin (email, expires_in_hours) |
| GET | /admin/tenants/{id}/audit | Get audit log for tenant |

### Public Invite Acceptance (no auth)
| Method | Path | Description |
|--------|------|-------------|
| POST | /invite/accept | Accept invite: code, password → create user as client_admin, mark invite used |

## Invite Code Design
- Cryptographically secure random string (32 bytes → 43 char base64url)
- One-time use: `used_at` set on accept
- Time-limited: `expires_at` (default 168 hours = 7 days)
- Tied to specific tenant and email
- On accept: create user with role=client_admin, tenant_id from invite, password_hash from request

## Suspend Semantics
- Update tenant status to `suspended`
- Immediately revoke ALL sessions for that tenant: `UPDATE sessions SET is_revoked=true, revoked_at=now() WHERE tenant_id=?`
- Login endpoint already checks tenant.status in (suspended, offboarding) → 403
- Reactivate: status=active (sessions already revoked, users must log in again)

## Audit Trail
Every admin action writes to audit_logs:
- `create_tenant`: actor=super_admin, target=tenant, details={short_code, name, storage_quota_mb}
- `suspend_tenant`: actor=super_admin, target=tenant, details={}
- `reactivate_tenant`: actor=super_admin, target=tenant, details={}
- `create_invite`: actor=super_admin, target=invite, details={email, expires_at}
- `accept_invite`: actor=system (no user yet), target=user, details={email, invite_id}

## Error Handling
- Tenant short_code uniqueness enforced by DB
- Invite code uniqueness enforced by DB
- Expired/invalid/used invite → 400/404 (no enumeration)
- Suspend non-existent tenant → 404
- Reactivate non-suspended tenant → 400

## Tests to Write
1. Create tenant → verify audit log
2. Create duplicate short_code → 409/400
3. Suspend tenant → verify sessions revoked, login blocked
4. Reactivate tenant → verify login works
5. Create invite → verify code returned, audit log
6. Accept invite → verify user created as client_admin, invite marked used
7. Reuse invite → 400
8. Expired invite → 400
9. Cross-tenant: admin A cannot suspend tenant B (RLS)
10. Router walk: all new endpoints in ROLE_MATRIX

## Risks
- Audit log RLS: super_admin writes via admin API which sets tenant context. Ensure set_tenant_context called before write.
- Invite acceptance: no tenant context (public endpoint), must not use RLS-dependent queries. Use admin connection or disable RLS for that query.
- Session revocation on suspend: must use admin connection to bypass RLS and revoke ALL sessions for the tenant.

## Gate 1 Checklist
- [x] Endpoints defined
- [x] Invite code design specified
- [x] Suspend semantics defined
- [x] Audit trail design
- [x] Migration plan
- [x] Test plan
- [x] Risks identified