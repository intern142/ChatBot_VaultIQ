# Approach Note — VQ-304: Tenant Settings Storage and Validation

## Objective
Each client can adjust VaultIQ within limits we control, and those adjustments are stored safely.

## Acceptance Criteria
1. Client Admin can set: display name, logo (validated image, size-limited, stored in tenant's storage), accent colour, custom 'not found' message (plain text, length-limited), allowed upload formats, conversation retention days
2. Storage quota is visible to Client Admin but only Super Admin can change it
3. Every setting is validated; a bad value is rejected with a clear reason
4. Changes are audited
5. Public lookup by organisation code returns only name, logo and colour, and behaves identically for a code that does not exist

## Database Design

### New Table: `tenant_settings`
```sql
CREATE TABLE tenant_settings (
    tenant_id UUID PRIMARY KEY REFERENCES tenants(id) ON DELETE CASCADE,
    display_name VARCHAR(255),
    logo_path VARCHAR(500),              -- path within tenant's storage
    accent_colour VARCHAR(7),            -- #RRGGBB hex
    not_found_message TEXT,              -- plain text, max 500 chars
    allowed_upload_formats JSONB,        -- array of mime types e.g. ["application/pdf", "text/plain"]
    conversation_retention_days INTEGER, -- 1-3650 (10 years)
    updated_by UUID REFERENCES users(id),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### RLS Policy
- FORCE ROW LEVEL SECURITY
- Policy: `tenant_id = current_setting('app.current_tenant', true)::uuid`
- Grant SELECT, INSERT, UPDATE to `vaultiq_app`
- Super Admin reads via separate endpoint with elevated perms

## API Endpoints

### Admin Router (super_admin only)
- `PATCH /admin/tenants/{id}/settings` — Super Admin can change ANY setting including storage_quota_mb
- `GET /admin/tenants/{id}/settings` — Super Admin reads all settings

### Client Admin Router (client_admin only)
- `PATCH /tenant/settings` — Client Admin sets their tenant's settings (no storage_quota_mb)
- `GET /tenant/settings` — Client Admin reads their tenant's settings

### Public Router (no auth)
- `GET /tenants/{short_code}/public` — Returns `{ name, logo_path, accent_colour }` only; identical 200 for non-existent codes

## Validation Rules

| Field | Validation |
|-------|------------|
| display_name | 1-255 chars |
| logo | Image file (png/jpg/webp), max 500KB, dimensions max 512x512 |
| accent_colour | Hex format `#RRGGBB` or `#RGB` |
| not_found_message | Plain text, max 500 chars, no HTML/markdown |
| allowed_upload_formats | Subset of system allowlist (19 formats from VQ-201) |
| conversation_retention_days | Integer 1-3650 |

## File Storage
- Logo stored at: `storage/{tenant_id}/settings/logo.{ext}`
- Uses existing `storage.py` service with tenant isolation
- Path never derived from user filename

## Audit Trail
- Every settings change writes to `audit_logs`:
  - action: `update_tenant_settings`
  - target_type: `tenant`
  - target_id: tenant_id
  - details: `{ field: old_value, new_value }` JSONB

## Implementation Plan

### Files to Create/Modify
1. **Migration**: `alembic/versions/xxx_vq_304_add_tenant_settings.py`
2. **Model**: `app/models/tenant_settings.py`
3. **Schema**: `app/schemas/tenant_settings.py` (Pydantic models for validation)
4. **Service**: `app/services/tenant_settings.py` (validation, logo processing, audit)
5. **Routes**:
   - `app/routes/admin.py` — add settings endpoints
   - `app/routes/tenant.py` — new file for client_admin settings
   - `app/routes/public.py` — new file for public lookup
6. **Tests**: `tests/test_tenant_settings.py`

### Steps
1. Write migration with table, RLS, grants
2. Create model with relationships
3. Create Pydantic schemas with validation
4. Implement service (validation, file handling, audit)
5. Add endpoints with role-based permissions (`require_roles`)
6. Write tests covering all ACs + malicious inputs
7. Run full test suite
8. Gate 4: Self-review
9. Gate 6: Live container verify

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Logo upload bypasses validation | Validate MIME + dimensions + size server-side; use libmagic like VQ-201 |
| XSS via not_found_message | Store as plain text; never render as HTML; validate no markup |
| Client Admin changes storage quota | Exclude `storage_quota_mb` from Client Admin schema; only in Super Admin schema |
| Public lookup leaks tenant existence | Return identical 200 response for valid and invalid codes; log only internally |
| Cross-tenant logo access | RLS on table + storage path includes tenant_id |

## Tests to Write

1. Client Admin can update each setting individually
2. Validation rejects: oversized logo, non-image, bad hex, HTML in message, invalid mime, retention out of range
3. Super Admin can change storage_quota_mb; Client Admin cannot
4. Audit log written on every change
5. Public lookup returns only name/logo/colour; identical response for unknown code
6. RLS enforcement: tenant A cannot read/write tenant B settings
7. Logo stored in correct tenant-isolated path
8. Malicious file (PHP with image header) rejected

## Dependencies
- VQ-107 ✅ (tenant lifecycle, admin router, audit_logs)
- VQ-201 ✅ (file validation patterns, storage service, MIME detection)
- VQ-106 ✅ (permissions matrix, require_roles)
- VQ-104 ✅ (per-tenant storage, storage service)

## Gate 1 Checklist
- [x] Tables to touch identified
- [x] Migration steps outlined
- [x] Tests planned
- [x] Risks identified
- [x] Dependencies confirmed complete

**Ready for reviewer approval before coding.**