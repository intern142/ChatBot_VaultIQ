"""VQ-110: Isolation test route manifest — single source of truth for coverage guard.

Every tenant-scoped operation must be listed here. Adding a new route to the app
without adding it here will cause test_route_coverage_guard to fail.
"""

ISOLATION_COVERED_ROUTES = {
    # Public (no auth) — still test they don't leak cross-tenant info
    ("GET", "/health"),
    ("POST", "/auth/login"),
    ("POST", "/invite/accept"),

    # Authenticated — any role
    ("POST", "/auth/refresh"),
    ("POST", "/auth/logout"),

    # Password reset — public (no auth), still must not leak cross-tenant info
    ("POST", "/auth/reset-password"),

    # Documents — tenant users only (super_admin DENIED by permissions)
    ("POST", "/documents"),
    ("GET", "/documents"),
    ("GET", "/documents/usage"),
    ("GET", "/documents/{document_id}/preview"),
    ("GET", "/documents/{document_id}/download"),
    ("DELETE", "/documents/{document_id}"),

    # Documents — VQ-202 approval workflow (client_admin only)
    ("POST", "/documents/{document_id}/approve"),
    ("POST", "/documents/{document_id}/reject"),
    ("GET", "/documents/{document_id}/versions"),
    ("GET", "/documents/searchable/approved"),

    # Search — tenant users only
    ("POST", "/search"),
    ("GET", "/search/suggest"),

    # Answers — tenant users only (extractive answer engine)
    ("POST", "/answers"),

    # Answers feedback — tenant users only
    ("POST", "/answers/{answer_id}/feedback"),
    ("PATCH", "/answers/{answer_id}/feedback"),
    ("GET", "/answers/{answer_id}/feedback"),
    ("GET", "/answers/feedback"),

    # Users management — client_admin of their own tenant
    ("GET", "/users/audit"),
    ("PATCH", "/users/{user_id}/role"),
    ("POST", "/users/import"),
    ("POST", "/users/invites"),
    ("POST", "/users/{user_id}/deactivate"),
    ("POST", "/users/{user_id}/password-reset"),
    ("POST", "/users/{user_id}/reactivate"),

    # Admin — super_admin only
    ("POST", "/admin/tenants"),
    ("GET", "/admin/tenants"),
    ("PATCH", "/admin/tenants/{tenant_id}/suspend"),
    ("PATCH", "/admin/tenants/{tenant_id}/reactivate"),
    ("POST", "/admin/tenants/{tenant_id}/invite"),
    ("GET", "/admin/tenants/{tenant_id}/audit"),

    # Admin tenant settings — super_admin only
    ("GET", "/admin/tenants/{tenant_id}/settings"),
    ("PATCH", "/admin/tenants/{tenant_id}/settings"),
    ("POST", "/admin/tenants/{tenant_id}/settings/logo"),

    # Admin Platform — super_admin only (platform-wide, metadata only)
    ("GET", "/admin/platform/overview"),
    ("GET", "/admin/platform/overview/{tenant_id}"),
    ("GET", "/admin/platform/health"),
    ("GET", "/admin/platform/stats"),

    # Audit trail export — client_admin of their own tenant (VQ-402)
    ("GET", "/audit/export"),

    # Offboarding & deletion reports — super_admin only (VQ-403)
    ("PATCH", "/admin/tenants/{tenant_id}/offboard"),
    ("PATCH", "/admin/tenants/{tenant_id}/cancel-offboarding"),
    ("GET", "/admin/deletion-reports"),
    ("GET", "/admin/deletion-reports/{report_id}"),
}


def normalize_path(path: str) -> str:
    """Normalize path params to manifest format."""
    return path
