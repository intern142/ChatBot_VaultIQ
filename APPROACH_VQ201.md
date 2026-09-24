# VQ-201 Approach Note — Document upload, tenant-scoped, with quota

## Current State (VQ-104)
- POST /documents uploads files to `storage/{tenant_id}/{doc_uuid}/original/{uuid}.bin`
- Allowed MIME types: PDF, TXT, MD, DOCX, XLSX, CSV (7 types)
- 50MB max file size (validated from `file.size` header)
- Path traversal sanitized (filename never used in path)
- Cross-tenant access returns 404 (RLS + code checks)
- Storage usage tracked via GET /documents/usage
- Both client_admin AND employee can upload (per ROLE_MATRIX)
- Tenant model has `storage_quota_mb` column (nullable, not enforced)

## VQ-201 Requirements
1. **12 formats + OCR** — support all HeXta formats (need to identify which 12)
2. **Category per upload** — Policy / HR / SOP / Process / Other
4. **Per-file size limit + per-tenant quota** — reject before write, clear error
5. **Content-based MIME detection** — python-magic or similar, not just header
6. **Employee upload blocked** — only client_admin

## Implementation Plan

### 1. Database Migration (007_vq201_document_category_quota.py)
- Add `category` column to `documents` table (enum: policy, hr, sop, process, other)
- Make `storage_quota_mb` on tenants non-nullable with default (e.g., 2048 MB)

### 2. MIME Detection from Content
- Add `python-magic` (libmagic wrapper) for content-based MIME detection
- Validate uploaded file's actual content matches allowed types
- Keep header-based check as fast reject, add content-based as authoritative

### 3. Category Parameter
- Add `category` form field to POST /documents (required, enum)
- Update Document model, schema, response

### 4. Quota Enforcement
- Before saving file: compute current tenant usage + new file size
- Compare against `tenant.storage_quota_mb`
- If exceeded: return 413 with clear message, write nothing

### 5. Per-File Size Limit
- Keep 50MB default, make configurable via settings
- Check before quota (fail fast)

### 6. Role Restriction
- Update ROLE_MATRIX: POST /documents → {"client_admin"} only
- Update endpoint dependency: `require_roles_with_tenant("client_admin")`

### 7. Allowed MIME Types Expansion
- Research HeXta's 12 formats + OCR path
- Likely additions: PPTX, ODT, ODS, RTF, EPUB, MSG, EML, TIFF (OCR), PNG/JPG (OCR)

### 8. Tests
- Quota exceeded (413, no file written)
- MIME mismatch (content vs header)
- Employee 403
- Category required/validated
- All 12 formats accepted
- OCR path (if applicable)

## Files to Touch
- `alembic/versions/007_vq201_document_category_quota.py` — new migration
- `app/models/document.py` — add category column
- `app/schemas/document.py` — add category to DocumentCreate/Response
- `app/routes/documents.py` — upload logic: MIME detection, quota, category, role
- `app/auth/permissions.py` — update ROLE_MATRIX for POST /documents
- `app/services/storage.py` — no changes needed (quota check before save)
- `app/config.py` — add MAX_FILE_SIZE setting, allowed MIME list from content
- `tests/test_documents.py` — new test cases
- `requirements.txt` — add python-magic

## Risks
- `python-magic` requires libmagic system library (Dockerfile may need update)
- Quota check race condition: two concurrent uploads could both pass check — acceptable for v1, mitigate with DB constraint later
- OCR path: unclear what "scanned-document (OCR) path" means — may be separate endpoint or just accepting image MIME types

## Test Strategy
- Unit: quota calc, MIME detection, category validation
- Integration: full upload flow with quota, role, MIME checks
- Cross-tenant: ensure quota isolation
- Live container: upload each format as Client Admin

## Order of Gates
1. Approach note → reviewer approval
2. Implement on branch vq-201-tenant-upload
3. Tests green (full suite)
4. Self-review checklist
5. Code review
6. Live container verify
7. Demo Friday