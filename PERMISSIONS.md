# VaultIQ Permissions Matrix

This document lists every operation in VaultIQ and what each role may do with it.

## Roles

| Role | Description |
|------|-------------|
| `super_admin` | Platform operator — no tenant, sees counts/storage only |
| `client_admin` | Tenant administrator — manages documents and staff |
| `employee` | Regular tenant user — asks questions, reads history, gives feedback |

## Permissions Matrix

| Endpoint | Method | Super Admin | Client Admin | Employee |
|----------|--------|-------------|--------------|----------|
| `/health` | GET | ✅ | ✅ | ✅ |
| `/auth/login` | POST | ✅ | ✅ | ✅ |
| `/auth/refresh` | POST | ✅ | ✅ | ✅ |
| `/auth/logout` | POST | ✅ | ✅ | ✅ |
| `/documents` | POST | ❌ | ✅ | ✅ |
| `/documents` | GET | ❌ | ✅ | ✅ |
| `/documents/usage` | GET | ❌ | ✅ | ❌ |
| `/documents/{id}/preview` | GET | ❌ | ✅ | ✅ |
| `/documents/{id}/download` | GET | ❌ | ✅ | ✅ |
| `/documents/{id}` | DELETE | ❌ | ✅ | ❌ |

## Rules

1. **Super Admin is explicitly denied** on all `/documents/*` endpoints — returns 403
2. **Employees cannot** manage storage usage or delete documents
3. **Unauthenticated users** can only access `/health` and `/auth/login`
4. Adding a new endpoint **without** declaring its permissions in `app/auth/permissions.py` causes the router walk test to fail

## Enforcement

Permissions are enforced via:
- `require_roles(*allowed_roles)` — for endpoints using `get_current_user`
- `require_roles_with_tenant(*allowed_roles)` — for endpoints using `get_current_user_with_tenant`
- Inline role checks in endpoints with raw token parsing (e.g., `/auth/logout`)

Source of truth: `app/auth/permissions.py` → `ROLE_MATRIX` dict
