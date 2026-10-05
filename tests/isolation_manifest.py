"""VQ-110: Isolation test route manifest — single source of truth for coverage guard.

Every tenant-scoped operation must be listed here. Adding a new route to the app
without adding it here will cause test_route_coverage_guard to fail.
"""

ISOLATION_COVERED_ROUTES = {
    # Public (no auth) — still test they don't leak cross-tenant info
    ("GET", "/health"),
    ("POST", "/auth/login"),
    ("POST", "/invite/accept"),
    # VQ-301: unauthenticated, credential is a one-time code. Exercised with
    # tenant B's code against tenant A in test_password_reset.py.
    ("POST", "/auth/reset-password"),

    # Authenticated — any role
    ("POST", "/auth/refresh"),
    ("POST", "/auth/logout"),

    # Documents — tenant users only (super_admin DENIED by permissions)
    ("POST", "/documents"),
    ("GET", "/documents"),
    ("GET", "/documents/usage"),
    ("GET", "/documents/{document_id}/preview"),
    ("GET", "/documents/{document_id}/download"),
    ("DELETE", "/documents/{document_id}"),

# VQ-202: approval workflow and document versions
    ("POST", "/documents/{document_id}/approve"),
    ("POST", "/documents/{document_id}/reject"),
    ("GET", "/documents/{document_id}/versions"),
    ("GET", "/documents/searchable/approved"),

    # Feedback — tenant users only (super_admin DENIED by permissions)
    ("POST", "/answers/{answer_id}/feedback"),
    ("PATCH", "/answers/{answer_id}/feedback"),
    ("GET", "/answers/{answer_id}/feedback"),
    ("GET", "/answers/feedback"),

    # Admin — super_admin only
    ("POST", "/admin/tenants"),
    ("GET", "/admin/tenants"),
    ("PATCH", "/admin/tenants/{tenant_id}/suspend"),
    ("PATCH", "/admin/tenants/{tenant_id}/reactivate"),
    ("POST", "/admin/tenants/{tenant_id}/invite"),
    ("GET", "/admin/tenants/{tenant_id}/audit"),

    # VQ-301: Client Admin acting inside their own tenant. Cross-tenant issue
    # attempts are covered in test_password_reset.py::TestIssueCode.
    ("POST", "/users/{user_id}/password-reset"),

    # VQ-301: the rest of user management. Every one of these is reached with a
    # tenant A credential against a tenant B identifier in
    # test_user_management.py, and every response body is checked for tenant B
    # identifiers.
    ("POST", "/users/invites"),
    ("POST", "/users/import"),
    ("POST", "/users/{user_id}/deactivate"),
    ("POST", "/users/{user_id}/reactivate"),
    ("PATCH", "/users/{user_id}/role"),
    ("GET", "/users/audit"),
}


def normalize_path(path: str) -> str:
    """Normalize path params to manifest format."""
    return path