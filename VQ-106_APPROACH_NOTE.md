# VQ-106 Gate 1: Approach Note — Role and Permission Model

## Objective
Three roles (Super Admin, Client Admin, Employee) with a written, enforced matrix of what each may do. Adding a new endpoint without declaring permissions must cause a test failure.

## Permissions Matrix

| Endpoint | Method | Super Admin | Client Admin | Employee | Notes |
|----------|--------|-------------|--------------|----------|-------|
| `/health` | GET | ✅ | ✅ | ✅ | Public — no auth required |
| `/auth/login` | POST | ✅ | ✅ | ✅ | Public — no auth required |
| `/auth/refresh` | POST | ✅ | ✅ | ✅ | Any authenticated user |
| `/auth/logout` | POST | ✅ | ✅ | ✅ | Any authenticated user |
| `/documents` | POST | ❌ | ✅ | ✅ | Upload — tenant users only |
| `/documents` | GET | ❌ | ✅ | ✅ | List — tenant users only |
| `/documents/usage` | GET | ❌ | ✅ | ❌ | Storage stats — client_admin only |
| `/documents/{id}/preview` | GET | ❌ | ✅ | ✅ | Preview — tenant users only |
| `/documents/{id}/download` | GET | ❌ | ✅ | ✅ | Download — tenant users only |
| `/documents/{id}` | DELETE | ❌ | ✅ | ❌ | Delete — client_admin only |

**Key rule:** Super Admin is explicitly DENIED on all `/documents/*` endpoints (returns 403). This enforces acceptance criterion 4: "Super Admin is explicitly denied any operation that returns document text, chunks or chat content."

## Design: `require_roles()` Dependency Factory

### New file: `app/auth/permissions.py`

```python
from fastapi import Depends, HTTPException, status
from app.auth.dependencies import get_current_user, get_current_user_with_tenant
from app.models.user import User

def require_roles(*allowed_roles: str):
    """Dependency factory that checks the user's role against an allowlist.
    
    Usage:
        @router.get("/documents", dependencies=[Depends(require_roles("client_admin", "employee"))])
        async def list_documents(...):
    """
    async def _check(user: User = Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return user
    return _check
```

### Why this approach
1. **Composes with existing dependencies** — `get_current_user` already resolves the User object; we just check `.role`
2. **Declarative** — each endpoint declares its allowed roles in the decorator
3. **Fails safe** — forgetting to add `dependencies=[...]` means the endpoint has NO permission check, which the router walk test catches
4. **Uniform** — same mechanism for every endpoint

### For endpoints using `get_current_user_with_tenant`
Endpoints that need tenant context use `get_current_user_with_tenant` which returns `tuple[User, str]`. The role check will be integrated into the endpoint body using a helper:

```python
from app.auth.permissions import assert_role

@router.get("/documents")
async def list_documents(user_and_tenant = Depends(get_current_user_with_tenant)):
    user, tenant_id = user_and_tenant
    assert_role(user, "client_admin", "employee")
    ...
```

Or better: create `require_roles_with_tenant()` that wraps `get_current_user_with_tenant` and checks role.

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `app/auth/permissions.py` | **CREATE** | `require_roles()`, `require_roles_with_tenant()`, `assert_role()`, `ROLE_MATRIX` dict |
| `app/routes/auth.py` | MODIFY | Add `dependencies=[Depends(require_roles(...))]` to refresh/logout |
| `app/routes/documents.py` | MODIFY | Add role checks to every endpoint |
| `tests/test_permissions.py` | **CREATE** | Router walk test + denied-role tests |
| `PERMISSIONS.md` | **CREATE** | Human-readable permissions document (acceptance criterion 1) |

## Tests

### 1. Router Walk Test (acceptance criterion 3)
```python
def test_all_endpoints_have_permissions_declared():
    """Every endpoint must appear in ROLE_MATRIX. Adding a new endpoint without
    declaring its permissions causes this test to FAIL."""
    # Iterate all routes in app.routes, check each is in ROLE_MATRIX
```

### 2. Denied-Role Tests (per endpoint class)
For each endpoint in the matrix:
- Call with a role that should be DENIED → expect 403
- Call with a role that should be ALLOWED → expect 200/201

### 3. Specific Tests
- Super Admin on `/documents/*` → 403 (not 200 with empty results)
- Employee on `/documents/usage` → 403
- Employee on `/documents/{id}/delete` → 403
- Unauthenticated on protected endpoints → 401/403

## Risks

| Risk | Mitigation |
|------|------------|
| Router walk test misses endpoints added by future branches | Test iterates `app.routes` at runtime, not a static list |
| `get_current_user_with_tenant` returns different type than `get_current_user` | Create separate `require_roles_with_tenant()` for tuple-returning deps |
| Super Admin bypass in `get_current_user_with_tenant` lets them through RLS | Explicit role check BEFORE tenant context is set |

---

**Ready for reviewer approval before Gate 2 implementation.**
