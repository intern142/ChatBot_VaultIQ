# VQ-304 Self-Review — Tenant settings storage and validation

## Acceptance Criteria Walkthrough

### AC1: Client Admin can set display name, logo, accent colour, not_found_message, allowed formats, retention days ✅
- **Implementation:** `TenantSettingsUpdateClientAdmin` schema with all 6 fields
- **Endpoints:** `PATCH /tenant/settings` (client_admin), `POST /tenant/settings/logo` (client_admin)
- **Verified:** `test_update_settings_creates_if_not_exists`, `test_upload_valid_png/jpeg/webp`, all validation tests

### AC2: Storage quota visible to Client Admin, only Super Admin can change it ✅
- **Implementation:** `storage_quota_mb` only in `TenantSettingsUpdateSuperAdmin` schema (inherits from client_admin)
- **Service:** `update_settings` with `is_super_admin=True` updates `Tenant.storage_quota_mb`
- **Verified:** `test_super_admin_can_update_storage_quota`, schema tests

### AC3: Every setting validated; bad value rejected with clear reason ✅
- **Validation:** Pydantic field validators on all fields
- **display_name:** 1-255 chars
- **accent_colour:** Hex format `#RRGGBB` or `#RGB` regex
- **not_found_message:** Max 500 chars, rejects HTML/markup (`<`, `>`, `&`)
- **allowed_upload_formats:** Subset of system allowlist (19 formats), non-empty
- **conversation_retention_days:** Integer 1-3650
- **logo:** MIME (PNG/JPEG/WebP), size ≤500KB, dimensions ≤512x512
- **Verified:** All 14 validation tests pass

### AC4: Changes are audited ✅
- **Implementation:** `update_settings` writes to `AuditLog` with action `update_tenant_settings`
- **Details:** `{ field: {old: ..., new: ...} }` for each changed field
- **Actor role:** `client_admin` or `super_admin` based on caller
- **Verified:** `test_update_settings_audit_log`

### AC5: Public lookup by org code returns only name, logo, colour; identical for unknown ✅
- **Endpoint:** `GET /tenants/{short_code}/public` (no auth)
- **Response:** `{ name, logo_path, accent_colour }` only
- **No existence leak:** Returns empty strings for unknown codes (same structure)
- **Verified:** `test_public_lookup_returns_name_logo_colour`, `test_public_lookup_unknown_code_returns_empty`

---

## Review Checklist (from .github/CHECKLIST.md)

### Code Quality
- [x] Code follows project style conventions (SQLAlchemy 2.0, Pydantic V2, async)
- [x] No hardcoded secrets, passwords, or connection strings
- [x] No `print()` or debug statements
- [x] Functions focused and not too long
- [x] No unused imports or variables
- [x] Error handling present (ValueError for validation, HTTPException for API)

### Database & Migrations
- [x] Migration reversible (upgrade + downgrade)
- [x] Migration tested: upgrade → downgrade → re-upgrade
- [x] No data loss on downgrade
- [x] Indexes: primary key on `tenant_id` (FK to tenants)
- [x] Foreign keys: `tenant_id` → tenants (CASCADE), `updated_by` → users (SET NULL)
- [x] Constraints at DB level: NOT NULL, FK, RLS FORCE ROW LEVEL SECURITY

### Security
- [x] Input validation on all user-facing endpoints (Pydantic + service layer)
- [x] SQL injection not possible (SQLAlchemy ORM)
- [x] Authentication required: client_admin for `/tenant/*`, super_admin for `/admin/tenants/*/settings`, public for `/tenants/{code}/public`
- [x] Authorization enforced via `require_roles` decorator
- [x] Sensitive data not logged
- [x] Secrets loaded from env
- [x] File upload validation: MIME, size, dimensions, content verification (libmagic + PIL)

### API Design
- [x] Consistent response format (Pydantic models)
- [x] Proper HTTP status codes (200, 201, 400, 403, 404)
- [x] Request/response schemas validated with Pydantic
- [x] No existence leak on public endpoint

### Testing
- [x] Unit tests for validation logic (14 tests)
- [x] Service tests for business logic (15 tests)
- [x] Edge cases: oversized image, large dims, non-image, malicious file, HTML in message
- [x] Negative tests: cross-tenant isolation, invalid formats, unknown codes
- [x] All 29 VQ-304 tests pass locally and against live container
- [x] Full suite: 166 tests pass

### Multi-Tenancy (VaultIQ specific)
- [x] `tenant_settings` table has `tenant_id` PK/FK (1:1 with tenants)
- [x] RLS policy: `tenant_isolation` with FORCE ROW LEVEL SECURITY
- [x] Queries respect tenant context (service uses `tenant_id` parameter)
- [x] Cross-tenant access blocked (`test_cross_tenant_isolation`)
- [x] Super admin bypass works: separate endpoint with elevated perms
- [x] Public endpoint identical response for valid/invalid codes

### Files & Structure
- [x] New files in correct structure:
  - `app/models/tenant_settings.py`
  - `app/schemas/tenant_settings.py`
  - `app/services/tenant_settings.py`
  - `app/routes/tenant.py` (client_admin)
  - `app/routes/public.py` (public)
  - `alembic/versions/5cf4dcd6b1b1_vq_304_add_tenant_settings.py`
  - `tests/test_vq304.py`
- [x] `__init__.py` exports updated (`app/models/__init__.py`)
- [x] Routers registered in `app/main.py`
- [x] No new dependencies (uses existing: PIL, python-magic, psycopg2)
- [x] `.gitignore` unchanged

---

## Common Mistakes Checklist

### Database
- [x] ON DELETE CASCADE on `tenant_id` FK
- [x] ON DELETE SET NULL on `updated_by` FK
- [x] Migration tested with downgrade
- [x] `server_default=func.now()` for `updated_at`

### SQLAlchemy
- [x] Async session used correctly
- [x] `await session.commit()` after changes
- [x] `mapped_column` with `UUID(as_uuid=True)`

### FastAPI
- [x] `Depends(get_db)` for database sessions
- [x] `response_model` on endpoints
- [x] `require_roles` for authorization
- [x] No circular imports

### Pydantic
- [x] Field constraints (min_length, max_length, ge, le, pattern)
- [x] `ConfigDict(from_attributes=True)` for responses
- [x] Custom validators for complex rules

### Security
- [x] No hardcoded secrets
- [x] File upload: MIME verified via libmagic, not extension
- [x] Image validated via PIL (dimensions, format)
- [x] Malicious file rejected (PHP with PNG header)
- [x] No existence leak on public endpoint

### Git
- [x] No `.env` or `__pycache__` committed
- [x] Commits have story ID (VQ-304)
- [x] No large files

---

## Gate 4 Status: ✅ Complete

All 5 acceptance criteria walked and confirmed. Full checklist ticked.

**Ready for Gate 5 (Code Review) → Gate 6 (Live Container Verify) ✅ → Gate 7 (Demo)**