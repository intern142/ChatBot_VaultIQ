"""VQ-110: Isolation test route manifest — single source of truth for coverage guard.

Every tenant-scoped operation must be listed here. Adding a new route to the app
without adding it here will cause test_route_coverage_guard to fail.
"""

ISOLATION_COVERED_ROUTES = {
    # Public (no auth) — still test they don't leak cross-tenant info
    ("GET", "/health"),
    ("POST", "/auth/login"),
    ("POST", "/invite/accept"),
    ("GET", "/tenants/{short_code}/public"),

    # Authenticated — any role
    ("POST", "/auth/refresh"),
    ("POST", "/auth/logout"),

    # Tenant settings — client_admin of their own tenant (VQ-304)
    ("GET", "/tenant/settings"),
    ("PATCH", "/tenant/settings"),
    ("POST", "/tenant/settings/logo"),

    # Documents — tenant users only (super_admin DENIED by permissions)
    ("POST", "/documents"),
    ("GET", "/documents"),
    ("GET", "/documents/usage"),
    ("GET", "/documents/searchable/approved"),
    ("GET", "/documents/{document_id}/preview"),
    ("GET", "/documents/{document_id}/download"),
    ("GET", "/documents/{document_id}/versions"),
    ("GET", "/documents/{document_id}/status"),
    ("POST", "/documents/{document_id}/approve"),
    ("POST", "/documents/{document_id}/reject"),
    ("POST", "/documents/{document_id}/reprocess"),
    ("DELETE", "/documents/{document_id}"),

    # Search — tenant users only
    ("POST", "/search"),
    ("GET", "/search/suggest"),

    # Answers — tenant users only (extractive answer engine)
    ("POST", "/answers"),
    ("GET", "/answers/feedback"),
    ("GET", "/answers/{answer_id}/feedback"),
    ("POST", "/answers/{answer_id}/feedback"),
    ("PATCH", "/answers/{answer_id}/feedback"),

    # Dashboard — client_admin of their own tenant (VQ-302)
    ("GET", "/dashboard/overview"),
    ("GET", "/dashboard/overview/30d"),
    ("GET", "/dashboard/documents"),
    ("GET", "/dashboard/users"),
    ("GET", "/dashboard/audit"),
    ("GET", "/dashboard/feedback"),
    ("GET", "/dashboard/knowledge-gaps"),
    ("GET", "/dashboard/export/{entity}"),

    # Users — client_admin of their own tenant (VQ-301)
    ("GET", "/users/audit"),
    ("POST", "/users/import"),
    ("POST", "/users/invites"),
    ("PATCH", "/users/{user_id}/role"),
    ("POST", "/users/{user_id}/deactivate"),
    ("POST", "/users/{user_id}/reactivate"),
    ("POST", "/users/{user_id}/password-reset"),

    # Audit trail export — client_admin of their own tenant (VQ-402)
    ("GET", "/audit/export"),

    # Admin — super_admin only
    ("POST", "/admin/tenants"),
    ("GET", "/admin/tenants"),
    ("PATCH", "/admin/tenants/{tenant_id}/suspend"),
    ("PATCH", "/admin/tenants/{tenant_id}/reactivate"),
    ("PATCH", "/admin/tenants/{tenant_id}/offboard"),
    ("PATCH", "/admin/tenants/{tenant_id}/cancel-offboarding"),
    ("POST", "/admin/tenants/{tenant_id}/invite"),
    ("GET", "/admin/tenants/{tenant_id}/audit"),
    ("GET", "/admin/tenants/{tenant_id}/settings"),
    ("PATCH", "/admin/tenants/{tenant_id}/settings"),
    ("POST", "/admin/tenants/{tenant_id}/settings/logo"),
    ("GET", "/admin/deletion-reports"),
    ("GET", "/admin/deletion-reports/{report_id}"),

    # Admin Platform — super_admin only (platform-wide, metadata only) (VQ-303)
    ("GET", "/admin/platform/overview"),
    ("GET", "/admin/platform/overview/{tenant_id}"),
    ("GET", "/admin/platform/health"),
    ("GET", "/admin/platform/stats"),
}


def normalize_path(path: str) -> str:
    """Normalize path params to manifest format."""
    return path
