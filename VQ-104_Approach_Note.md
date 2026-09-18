# VQ-104 — Per-tenant document storage: Approach Note

## Problem Understanding
Build per-tenant document storage where:
- Files are physically separated by tenant on disk
- No user-supplied value (filename, path, etc.) influences storage location
- Read/preview/download re-verifies tenant ownership
- Per-tenant storage usage tracked for future quotas

## Proposed Approach

### 1. Path Layout
```
storage/
  {tenant_id}/
    {document_uuid}/
      original/          # uploaded file (server-generated name)
      metadata.json      # document metadata (original filename, size, mime, uploaded_by, uploaded_at)
```

- Root: `storage/` (configurable via env var `STORAGE_ROOT`)
- Tenant isolation: First path segment = tenant UUID
- Document identity: Second path segment = server-generated UUID (not user filename)
- File stored with server-generated name (e.g., `{uuid}.bin`), original filename stored only in metadata.json

### 2. Server-Generated Document Identity
- On upload: generate UUID v4 for document_id
- Store file as `{document_id}.bin` (or keep extension from mime type for convenience)
- Never use uploaded filename in filesystem path
- Metadata maps: document_id → {original_filename, mime_type, size, uploaded_by, tenant_id}

### 3. Sanitisation Rules
- Uploaded filename: used only for display/download, never for path
- Strip path traversal sequences (`..`, `/`, `\`) from any user input
- Validate mime type against allowlist
- Enforce max file size (configurable)
- Store file with safe generated name only

### 4. Tenant Re-check Points
| Operation | Check |
|-----------|-------|
| Upload | JWT tenant_id must match request tenant (already enforced by VQ-103 middleware) |
| List documents | Query filtered by tenant_id (RLS + explicit WHERE) |
| Preview/Download | Look up document by ID → verify document.tenant_id == request tenant_id → 404 if mismatch |
| Delete | Same as download |
| Storage stats | Aggregate by tenant_id |

### 5. Database Model (New Migration)
```sql
CREATE TABLE documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  original_filename TEXT NOT NULL,
  stored_filename TEXT NOT NULL,  -- server-generated
  mime_type TEXT NOT NULL,
  size_bytes BIGINT NOT NULL,
  uploaded_by UUID NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ DEFAULT now()
);

-- RLS policy
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON documents
  USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- Index for listing
CREATE INDEX idx_documents_tenant ON documents(tenant_id, created_at DESC);
```

### 6. Storage Usage Tracking
- `size_bytes` column on documents table
- Per-tenant usage = `SUM(size_bytes) WHERE tenant_id = X`
- Expose via GET `/documents/usage` endpoint for Client Admin dashboard

### 7. API Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | /documents | Upload file (multipart) |
| GET | /documents | List documents (paginated) |
| GET | /documents/{id}/preview | Preview (inline, first N chars if text) |
| GET | /documents/{id}/download | Download (attachment, original filename) |
| DELETE | /documents/{id} | Delete document |
| GET | /documents/usage | Storage usage for current tenant |

### 8. Test Strategy
| Test | Description |
|------|-------------|
| Path traversal in filename | Upload with `../../etc/passwd` → stored safely |
| Cross-tenant download | Tenant A token → Tenant B document ID → 404 |
| Cross-tenant preview | Same as above → 404 |
| Cross-tenant delete | Same as above → 404 |
| Filename not in path | Verify stored file path never contains user filename |
| Storage usage | Sum matches uploaded sizes |
| RLS enforcement | Raw SQL query without tenant context returns 0 rows |

### 9. Gate 6 Evidence Plan
1. Start live container
2. Login as Tenant A → upload `policy.pdf`
3. Inspect disk: `storage/{tenant_a_uuid}/{doc_uuid}/original/policy.pdf` (or similar)
4. Login as Tenant B → try download Tenant A's document ID → expect 404
5. Paste curl commands + responses + disk `ls -la` output

### 10. Uncertainties / Questions
1. **Preview implementation**: Return first N characters for text files? Return signed URL? Return base64 for small files?
2. **Large files**: Stream upload/download? Chunked storage?
3. **Virus scanning**: Out of scope for now?
4. **Versioning**: "Approved, versioned" mentioned in Week 3 — should documents table support versions now or later?

---

**Requesting approval to proceed to Gate 2 (Implementation).**