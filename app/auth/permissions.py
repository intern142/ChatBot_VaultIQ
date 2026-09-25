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
