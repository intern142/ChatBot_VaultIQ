# VQ-303 Approach Note: Super Admin Console Data (Metadata Only)

## Objective
Platform operators (Super Admins) can see the health and usage of every tenant **without ever seeing a single sentence of client content**. All data served through the limited platform database identity (`vaultiq_super_admin`) from VQ-102, which has no access to document text, chunks, or chat messages.

---

## Current State (from VQ-107, VQ-302)

| Component | Status |
|-----------|--------|
| Admin router (`/admin`) | Exists, `super_admin` only via `require_roles("super_admin")` |
| Tenant list | `GET /admin/tenants` — returns all tenants (no RLS) |
| Tenant audit log | `GET /admin/tenants/{id}/audit` — tenant-scoped, requires context |
| Dashboard router (`/dashboard`) | Exists, `client_admin` only, tenant-scoped, returns empty stubs |
| Database roles | `vaultiq_app` (NOBYPASSRLS, tenant-scoped), `vaultiq_super_admin` (limited grants: SELECT on tenants only) |
| Tables with content | `document_chunks` (content, embedding), `documents` (extracted_text), `conversations` (not yet), `messages` (not yet) |

---

## Design Decisions

### 1. New Endpoints: Platform-Wide Admin View
Super Admin needs a **platform-wide** view, not tenant-scoped. Endpoints should be under `/admin` (super_admin only):

| Endpoint | Purpose | Returns |
|----------|---------|---------|
| `GET /admin/tenants/overview` | All tenants summary | Array of tenant metadata + computed stats |
| `GET /admin/tenants/{tenant_id}/overview` | Single tenant detail | Same as list + time-series |
| `GET /admin/platform/health` | Platform health | DB, disk, processing queue, no-internet check |
| `GET /admin/platform/stats` | Platform-wide aggregates | Total tenants, users, docs, storage, questions |

### 2. Data Sources (Metadata Only — No Content)

| Metric | Source Table | Notes |
|--------|--------------|-------|
| Tenant status | `tenants.status` | Already in `GET /admin/tenants` |
| User count | `users` (role != super_admin) | Count per tenant |
| Document count | `documents` | Count per tenant |
| Storage used | `documents.size_bytes` SUM | Per tenant |
| Storage quota | `tenants.storage_quota_mb` | Already in tenant |
| Questions per day | `audit_logs` (action='question') | Count per day per tenant |
| Processing health | `indexing_jobs` status | Pending/processing/failed counts |
| Last activity | `audit_logs.created_at` MAX | Per tenant |
| Platform DB health | `pg_stat_database` / custom check | Connection, latency |
| Processing backlog | `indexing_jobs` WHERE status='pending' | Global count |
| Disk usage | `pg_database_size` + file system | Total + per-tenant |
| No-internet check | Attempt DNS/HTTP to external | Should fail (expected) |
| Error rate | `audit_logs` (failed actions) / total | Per tenant + platform |

### 3. Database Access: `vaultiq_super_admin` Role
- **Current grants**: `SELECT` on `tenants` only (from VQ-102)
- **Required additional grants**:
  - `SELECT` on `users` (count only, no content)
  - `SELECT` on `documents` (count, size_bytes only)
  - `SELECT` on `audit_logs` (count, created_at, action — NOT details/content)
  - `SELECT` on `indexing_jobs` (status counts)
  - `EXECUTE` on helper functions (for stats)

**Critical**: Never grant access to `document_chunks.content`, `documents.extracted_text`, `conversations`, `messages`.

### 4. Time-Series Data
For "over time" metrics (questions per day, storage growth):
- Aggregate in SQL (PostgreSQL `date_trunc`, `generate_series`)
- Return arrays: `[{"date": "2026-10-01", "count": 42}, ...]`
- Default 30 days, configurable via query param

### 5. Schema Additions
New Pydantic schemas in `app/schemas/admin.py`:

```python
class TenantOverview(BaseModel):
    id: UUID
    short_code: str
    name: str
    status: TenantStatus
    user_count: int
    document_count: int
    storage_used_mb: float
    storage_quota_mb: int
    questions_24h: int
    questions_30d: int
    last_activity: datetime | None
    processing_pending: int
    processing_failed: int

class PlatformHealth(BaseModel):
    database: dict  # latency_ms, connections, size_mb
    disk: dict  # total_mb, used_mb, free_mb
    processing: dict  # pending, processing, failed
    no_internet: bool  # True = isolated (good)
    error_rate_24h: float

class PlatformStats(BaseModel):
    total_tenants: int
    active_tenants: int
    total_users: int
    total_documents: int
    total_storage_mb: float
    total_questions_24h: int
    total_questions_30d: int
```

### 6. Security: No Content Leakage
- **Automated test**: Scan every Super Admin response for content-like fields (`content`, `extracted_text`, `embedding`, `message`, `answer`, `question`)
- **Database test**: Verify `vaultiq_super_admin` cannot `SELECT` from `document_chunks.content`, `documents.extracted_text`
- **Response validation**: All endpoints return only metadata schemas

---

## Files to Create/Modify

### New Files
| File | Purpose |
|------|---------|
| `app/schemas/admin.py` | Super Admin response schemas (TenantOverview, PlatformHealth, PlatformStats) |
| `app/routes/admin_dashboard.py` | New router for platform-wide admin endpoints |
| `app/services/platform_stats.py` | Aggregation queries (SQL, no ORM for performance) |
| `alembic/versions/011_super_admin_grants.py` | Grant SELECT on metadata tables to `vaultiq_super_admin` |
| `tests/test_admin_dashboard.py` | Unit + integration tests |

### Modified Files
| File | Change |
|------|--------|
| `app/main.py` | Include `admin_dashboard_router` |
| `tests/isolation_manifest.py` | Add new admin endpoints to coverage |
| `tests/test_isolation_suite.py` | Add Super Admin content leakage tests |
| `.github/CHECKLIST.md` | Add "Super Admin responses scanned for content fields" |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Content accidentally returned | Automated test scans all responses; DB grants exclude content columns |
| `vaultiq_super_admin` gets too much access | Grant only `SELECT` on specific columns via views or column-level grants |
| Performance: counting across all tenants | Materialized views or async aggregation; cache 60s |
| Time-series queries slow | Use `generate_series` + left join; pre-aggregate in background job |
| No-internet check false positive | Check known-fail endpoint (e.g., `http://10.255.255.1/`) |

---

## Tests to Write

1. **Unit**: `platform_stats.py` functions with mocked DB
2. **Integration**: `/admin/tenants/overview` returns all tenants with correct counts
3. **Integration**: `/admin/platform/health` returns all health components
4. **Content leakage**: Every Super Admin endpoint response scanned for forbidden fields
5. **DB grants**: `vaultiq_super_admin` cannot select `document_chunks.content`
5. **Isolation suite**: Cross-tenant checks (Super Admin sees all, but no content)

---

## Gate 3 Acceptance (Tests Green)
- All new tests pass
- Full existing suite stays green
- Isolation suite covers new admin endpoints
- Content leakage test passes

---

## Gate 6 Evidence (Live Container)
- Create 3 tenants with varied data
- Login as Super Admin
- Call `/admin/tenants/overview` — verify counts match reality, no content
- Call `/admin/platform/health` — verify all components present
- Attempt to access content via Super Admin token — verify denied/empty

---

## Questions for Reviewer

1. **Endpoint structure**: `/admin/tenants/overview` (list) + `/admin/tenants/{id}/overview` (detail) vs separate `/admin/platform/*`? Prefer `/admin/platform/*` for platform-wide.
2. **Time-series granularity**: Daily buckets OK, or need hourly?
3. **Caching**: 60s TTL for stats, or real-time?
4. **No-internet check**: What target to ping? (Suggest: known RFC1918 address that should fail)
5. **Disk usage**: `pg_database_size('vaultiq')` + `storage/` filesystem, or just DB?

---

**Ready for Gate 1 approval. Shall I proceed to Gate 2 (Implementation)?**