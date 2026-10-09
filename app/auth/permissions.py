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

    # Password reset — public (no auth), one-time code issued by a Client Admin
    ("POST", "/auth/reset-password"): {"super_admin", "client_admin", "employee"},

    # Documents — tenant users only (super admin DENIED)
    ("POST", "/documents"): {"client_admin", "employee"},
    ("GET", "/documents"): {"client_admin", "employee"},
    ("GET", "/documents/usage"): {"client_admin"},
    ("GET", "/documents/{document_id}/preview"): {"client_admin", "employee"},
    ("GET", "/documents/{document_id}/download"): {"client_admin", "employee"},
    ("DELETE", "/documents/{document_id}"): {"client_admin"},

    # Documents — VQ-202 approval workflow (client_admin only)
    ("POST", "/documents/{document_id}/approve"): {"client_admin"},
    ("POST", "/documents/{document_id}/reject"): {"client_admin"},
    ("GET", "/documents/{document_id}/versions"): {"client_admin"},
    ("GET", "/documents/searchable/approved"): {"client_admin", "employee"},

    # Search & answers — tenant users only (super admin DENIED)
    ("POST", "/search"): {"client_admin", "employee"},
    ("GET", "/search/suggest"): {"client_admin", "employee"},
    ("POST", "/answers"): {"client_admin", "employee"},

    # Answers feedback — tenant users only
    ("POST", "/answers/{answer_id}/feedback"): {"client_admin", "employee"},
    ("PATCH", "/answers/{answer_id}/feedback"): {"client_admin", "employee"},
    ("GET", "/answers/{answer_id}/feedback"): {"client_admin", "employee"},
    ("GET", "/answers/feedback"): {"client_admin"},

    # Users management — client_admin of their own tenant (VQ-208/VQ-31x family)
    ("GET", "/users/audit"): {"client_admin"},
    ("PATCH", "/users/{user_id}/role"): {"client_admin"},
    ("POST", "/users/import"): {"client_admin"},
    ("POST", "/users/invites"): {"client_admin"},
    ("POST", "/users/{user_id}/deactivate"): {"client_admin"},
    ("POST", "/users/{user_id}/password-reset"): {"client_admin"},
    ("POST", "/users/{user_id}/reactivate"): {"client_admin"},

    # Dashboard — client_admin of their own tenant (VQ-208)
    ("GET", "/dashboard/overview"): {"client_admin"},
    ("GET", "/dashboard/overview/30d"): {"client_admin"},
    ("GET", "/dashboard/documents"): {"client_admin"},
    ("GET", "/dashboard/users"): {"client_admin"},
    ("GET", "/dashboard/audit"): {"client_admin"},
    ("GET", "/dashboard/feedback"): {"client_admin"},
    ("GET", "/dashboard/knowledge-gaps"): {"client_admin"},
    ("GET", "/dashboard/export/{entity}"): {"client_admin"},

    # Admin — super_admin only
    ("POST", "/admin/tenants"): {"super_admin"},
    ("GET", "/admin/tenants"): {"super_admin"},
    ("PATCH", "/admin/tenants/{tenant_id}/suspend"): {"super_admin"},
    ("PATCH", "/admin/tenants/{tenant_id}/reactivate"): {"super_admin"},
    ("POST", "/admin/tenants/{tenant_id}/invite"): {"super_admin"},
    ("GET", "/admin/tenants/{tenant_id}/audit"): {"super_admin"},
    ("GET", "/admin/tenants/{tenant_id}/settings"): {"super_admin"},
    ("PATCH", "/admin/tenants/{tenant_id}/settings"): {"super_admin"},
    ("POST", "/admin/tenants/{tenant_id}/settings/logo"): {"super_admin"},

    # Tenant settings — client_admin only
    ("GET", "/tenant/settings"): {"client_admin"},
    ("PATCH", "/tenant/settings"): {"client_admin"},
    ("POST", "/tenant/settings/logo"): {"client_admin"},

    # Public tenant lookup — no auth
    ("GET", "/tenants/{short_code}/public"): {"super_admin", "client_admin", "employee"},

    # Admin Platform — super_admin only (platform-wide, metadata only)
    ("GET", "/admin/platform/overview"): {"super_admin"},
    ("GET", "/admin/platform/overview/{tenant_id}"): {"super_admin"},
    ("GET", "/admin/platform/health"): {"super_admin"},
    ("GET", "/admin/platform/stats"): {"super_admin"},

    # Audit trail export — client_admin of their own tenant only
    ("GET", "/audit/export"): {"client_admin"},

    # Offboarding & deletion reports — super_admin only (VQ-403)
    ("PATCH", "/admin/tenants/{tenant_id}/offboard"): {"super_admin"},
    ("PATCH", "/admin/tenants/{tenant_id}/cancel-offboarding"): {"super_admin"},
    ("GET", "/admin/deletion-reports"): {"super_admin"},
    ("GET", "/admin/deletion-reports/{report_id}"): {"super_admin"},
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
