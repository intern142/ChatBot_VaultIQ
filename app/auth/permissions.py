"""VQ-106: Role-based permission enforcement.

Every endpoint must declare its allowed roles via require_roles() or
require_roles_with_tenant(). The ROLE_MATRIX provides a single source of truth
for the permissions document and the router walk test.
"""

from typing import Sequence
from fastapi import Depends, HTTPException, status
from app.auth.dependencies import get_current_user, get_current_user_with_tenant
from app.models.user import User


# ---------------------------------------------------------------------------
# Permissions matrix — single source of truth
# Key: (method, path)  Value: set of allowed roles
# ---------------------------------------------------------------------------

ROLE_MATRIX: dict[tuple[str, str], set[str]] = {
    # Public endpoints (no auth required)
    ("GET", "/health"): {"super_admin", "client_admin", "employee"},
    ("POST", "/auth/login"): {"super_admin", "client_admin", "employee"},
    ("POST", "/invite/accept"): {"super_admin", "client_admin", "employee"},  # Public - no auth
    # VQ-301: unauthenticated, but the only credential is a 256-bit one-time
    # code. Listed for all three roles because the matrix is the declaration
    # of what may call the operation, and the role is whatever the code's owner
    # is; the code, not the role, is the authorisation.
    ("POST", "/auth/reset-password"): {"super_admin", "client_admin", "employee"},

    # Auth — any authenticated user
    ("POST", "/auth/refresh"): {"super_admin", "client_admin", "employee"},
    ("POST", "/auth/logout"): {"super_admin", "client_admin", "employee"},

    # Documents — tenant users only (super admin DENIED, employee DENIED on upload)
    ("POST", "/documents"): {"client_admin"},
    ("GET", "/documents"): {"client_admin", "employee"},
    ("GET", "/documents/usage"): {"client_admin"},
    ("GET", "/documents/{document_id}/preview"): {"client_admin", "employee"},
    ("GET", "/documents/{document_id}/download"): {"client_admin", "employee"},
    ("DELETE", "/documents/{document_id}"): {"client_admin"},

    # Admin — super_admin only
    ("POST", "/admin/tenants"): {"super_admin"},
    ("GET", "/admin/tenants"): {"super_admin"},
    ("PATCH", "/admin/tenants/{tenant_id}/suspend"): {"super_admin"},
    ("PATCH", "/admin/tenants/{tenant_id}/reactivate"): {"super_admin"},
    ("POST", "/admin/tenants/{tenant_id}/invite"): {"super_admin"},
    ("GET", "/admin/tenants/{tenant_id}/audit"): {"super_admin"},

    # VQ-301: Client Admin acting inside their own tenant. Super Admin is
    # excluded on purpose (VQ-106 AC4 reserves tenant-scoped user management for
    # the client), and it is not under /admin so the VQ-107 invariant that every
    # /admin operation is Super Admin only stays true without an exception.
    ("POST", "/users/{user_id}/password-reset"): {"client_admin"},
    ("POST", "/users/invites"): {"client_admin"},
    ("POST", "/users/import"): {"client_admin"},
    ("POST", "/users/{user_id}/deactivate"): {"client_admin"},
    ("POST", "/users/{user_id}/reactivate"): {"client_admin"},
    ("PATCH", "/users/{user_id}/role"): {"client_admin"},
    ("GET", "/users/audit"): {"client_admin"},
}


def require_roles(*allowed_roles: str):
    """Dependency factory: check the authenticated user's role.

    Use in endpoint signatures:
        @router.get("/foo", dependencies=[Depends(require_roles("client_admin"))])
    """

    async def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return _check


def require_roles_with_tenant(*allowed_roles: str):
    """Dependency factory: check role for endpoints using get_current_user_with_tenant.

    Returns tuple[User, str] like the underlying dependency, after role check.
    """

    async def _check(
        user_and_tenant: tuple[User, str] = Depends(get_current_user_with_tenant),
    ) -> tuple[User, str]:
        user, tenant_id = user_and_tenant
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user_and_tenant

    return _check
