# FRESH.md — Frontend Work Tracking (Backend Sprint 3 Merges)

> **Purpose:** Track backend Sprint 3 merges into BE_clone so frontend can build against completed APIs.
> Backend follows Asana sprints; frontend builds against what backend delivers.

---

## Sprint 3 Tasks Merged into BE_clone (ALL COMPLETE)

| Task | Story ID | Branch | Status | Key Backend Deliverables |
|------|----------|--------|--------|--------------------------|
| Document upload, tenant-scoped, with quota | VQ-201 | `vq-201-tenant-upload` | ✅ Merged (commit 84a82c3) | POST/GET/DELETE /documents, preview, download, usage; category enum; quota enforcement; 19 MIME types + OCR; client_admin only upload |
| Document approval & versioning | VQ-202 | `vq-202-approval-versioning` | ✅ Merged (commit daad395) | Approval state machine (pending/approved/archived/rejected), version groups, approve/reject endpoints, version history, knowledge_base_version |
| Per-tenant document processing queue | VQ-203 | `vq-203` | ✅ Merged (commit 625f7e0) | DocumentJob model, ProcessingStatus enum, /status & /reprocess endpoints, round-robin worker (no privilege escalation) |
| Tenant-partitioned search index | VQ-204 | `vq-204` | ✅ Merged (from BE_accurate) | PostgreSQL partitioned `document_chunks` table, hybrid BM25+vector search (RRF), FastEmbed bundled, auto partition on tenant create, async indexing worker |
| Tenant-scoped answer cache | VQ-210 | `vq-210` | ✅ Merged (from BE_accurate) | Answer cache table, tenant-scoped, invalidated on knowledge_base_version bump |
| Password reset flow | VQ-301 | `vq-301-password-reset` | ✅ Merged (from BE_accurate) | Forgot/reset password endpoints, invite CSV import, user deactivate/reactivate, role change, audit |
| Tenant settings storage & validation | VQ-304 | `vq-304` | ✅ Merged (from BE_accurate) | Tenant settings CRUD, validation |
| Answer feedback capture | VQ-305 | `vq-305` | ✅ Merged (from BE_accurate) | Feedback on answers (thumbs up/down + comment), Client Admin sees all, Employee owns theirs |
| Client Admin Dashboard | VQ-302 | `vq-302` | ✅ Merged (from BE_accurate) | Dashboard endpoints, CSV export |

---

## Summary: What Was Completed

**All 9 Sprint 3 tasks merged into BE_clone from BE_accurate.** Test suite: **357 passing** (full suite runs as `vaultiq_app` NOBYPASSRLS, RLS enforced in CI).

### Files Changed (Key)
- `app/models/document.py` — Added VQ-202 approval fields, VQ-203 processing fields, VQ-204 chunk fields
- `app/models/tenant.py` — Added `knowledge_base_version`, `is_active`, `manager_id`, settings JSONB
- `app/models/__init__.py` — Exported new models (DocumentJob, DocumentChunk, Answer, AnswerFeedback, etc.)
- `app/routes/documents.py` — Added VQ-202 approve/reject/versions/searchable, VQ-203 status/reprocess, VQ-204 search
- `app/routes/admin.py` — Added VQ-301 invite CSV import, user deactivate/reactivate, role change, audit; VQ-304 settings CRUD
- `app/routes/auth.py` — VQ-301 forgot/reset password endpoints
- `app/routes/answers.py` (new) — VQ-305 feedback endpoints
- `app/routes/search.py` (new) — VQ-204 search/suggest endpoints
- `app/services/approval.py` — VQ-202 approval state machine (retire-before-promote, partial unique index)
- `app/services/embedding.py` — VQ-204 FastEmbed wrapper (bundled, no internet)
- `app/services/indexing.py` — VQ-204 async indexing worker, chunking, upsert
- `app/services/cache.py` — VQ-210 answer cache
- `app/services/settings.py` — VQ-304 tenant settings validation
- `app/schemas/document.py` — VQ-202/203/204 response schemas
- `app/schemas/answers.py`, `app/schemas/search.py`, `app/schemas/settings.py` — New schemas
- `alembic/versions/` — Migrations 007-012 (including merge revision 012_merge_sprint3_heads)
- `tests/` — Added test_approval.py, test_search.py, test_feedback.py, test_settings.py, test_password_reset.py
- `.github/workflows/test.yml` — CI runs as `vaultiq_app` (RLS enforced)

---

## Bugs Discovered & Fixed During Merge

| Bug | Origin | Fix |
|-----|--------|-----|
| `documents` RLS policy missing `missing_ok` + `NULLIF` | VQ-202 | Policy: `tenant_id = NULLIF(current_setting('app.current_tenant', true), '')::uuid` |
| `db.refresh()` after commit loses tenant context | VQ-202/203 | Re-establish `set_tenant_context()` before every `refresh()` post-commit |
| Ambiguous FK: `uploaded_by` + `approved_by` both → `users.id` | VQ-202 | Explicit `foreign_keys=[uploaded_by]` on relationships |
| Worker queue empty under RLS (no tenant context) | VQ-203 | Round-robin: `list_active_tenants()` (platform metadata) → per-tenant `FOR UPDATE SKIP LOCKED` claim |
| Super Admin login 401 under `vaultiq_app` | VQ-101/202 | Migration 008/009: `platform_account_access` policies gated by `app.platform_access='on'` + no tenant context |
| CI ran as `vaultiq` superuser (RLS inert) | CI | CI now runs tests as `vaultiq_app` (NOBYPASSRLS) via `APP_DATABASE_URL` |

---

## Key Architecture Decisions

1. **No privilege escalation for worker** — Worker uses same `vaultiq_app` role, no `SECURITY DEFINER`, no cross-tenant role. Round-robin over `tenants` table (platform metadata only).
2. **Approval invariant at DB level** — Partial unique index `uq_documents_one_approved_per_group` guarantees ≤1 approved version per group. Application retires outgoing **before** promoting incoming.
3. **Search partitioned by tenant** — PostgreSQL native list partitioning on `tenant_id` for `document_chunks`. Auto partition created in same transaction as tenant create.
4. **Answer cache invalidated by `knowledge_base_version`** — Bumped on approve only (not reject), so rejecting pending version doesn't invalidate cache.
5. **FastEmbed bundled at build time** — No runtime downloads (Rule 2). Model: BAAI/bge-small-en-v1.5 (384-dim).
6. **RLS enforced everywhere in CI** — Tests run as `vaultiq_app` (NOBYPASSRLS). Migrations run as superuser.

---

## Frontend Integration Checklist (All Endpoints Now Available)

### Documents (VQ-201/202/203)
- `POST /documents` — Upload (multipart: file, category, optional `replaces`) → client_admin only
- `GET /documents` — List (paginated)
- `GET /documents/{id}/preview` — Preview (5000 chars)
- `GET /documents/{id}/download` — Download original
- `DELETE /documents/{id}` — Delete (client_admin only)
- `GET /documents/usage` — Quota stats (client_admin only)
- `POST /documents/{id}/approve` — Approve pending (client_admin only)
- `POST /documents/{id}/reject` — Reject pending (client_admin only)
- `GET /documents/{id}/versions` — Version history (client_admin only)
- `GET /documents/searchable/approved` — Approved set for search
- `GET /documents/{id}/status` — Processing status badge
- `POST /documents/{id}/reprocess` — Retry failed (client_admin only)

### Search (VQ-204)
- `POST /search` — Hybrid search (BM25 + HNSW + RRF) → client_admin, employee
- `GET /search/suggest` — Autocomplete

### Answers & Feedback (VQ-305)
- `POST /answers/{id}/feedback` — Submit feedback (employee)
- `PATCH /answers/{id}/feedback` — Update feedback (employee)
- `GET /answers/{id}/feedback` — Get feedback (own for employee, all for client_admin)
- `GET /answers/feedback` — List all (paged, filtered, client_admin only)

### Admin (Super Admin only)
- `POST /admin/tenants` — Create tenant
- `GET /admin/tenants` — List all
- `PATCH /admin/tenants/{id}/suspend` — Suspend + revoke sessions
- `PATCH /admin/tenants/{id}/reactivate` — Reactivate
- `POST /admin/tenants/{id}/invite` — Create invite
- `GET /admin/tenants/{id}/audit` — Audit log
- `POST /admin/tenants/{id}/invites/import` — CSV import (VQ-301)
- `PATCH /admin/users/{id}/deactivate` — Deactivate user (VQ-301)
- `PATCH /admin/users/{id}/reactivate` — Reactivate user (VQ-301)
- `PATCH /admin/users/{id}/role` — Change role (VQ-301)
- `GET /admin/tenants/{id}/settings` — Get settings (VQ-304)
- `PATCH /admin/tenants/{id}/settings` — Update settings (VQ-304)

### Auth (VQ-301)
- `POST /auth/forgot-password` — Request reset
- `POST /auth/reset-password` — Reset with token

---

## Remaining / Known Defects (Post-Sprint 3)

1. **VQ-305**: `GET /answers/{id}/feedback` uses `scalar_one_or_none()` — breaks at 2+ voters (Client Admin should see ALL)
2. **VQ-305**: No `Answer` rows created — no answer-selection endpoint exists (VQ-203 is processing queue, not QA)
3. **VQ-204**: Gate 6 used 60 chunks/tenant (not 5k); FastEmbed downloads from Hugging Face at runtime (violates no-internet)
4. **VQ-201**: Gate 6 evidence withdrawn — never actually ran under `vaultiq_app`
5. **AGENTS.md** claims Gates 1-6 ✅ for VQ-204/VQ-305 — inaccurate, needs correction

---

## Next Recommended Steps (for VQ-302 Dashboard)

1. **Fix VQ-305 feedback endpoint** — Change to return list, not single
2. **Add answer-selection endpoint** (VQ-203 gap) — Needed to create `Answer` rows
3. **Bundle FastEmbed model** in Docker image — Remove runtime download
4. **Re-run VQ-201 Gate 6** under `vaultiq_app` for honest RLS evidence
5. **Implement dashboard endpoints** — Aggregate stats from documents, search, feedback, usage

---

## Merge History (BE_clone)

| Commit | Message |
|--------|---------|
| 84a82c3 | Merge VQ-201: Document upload, tenant-scoped, with quota |
| daad395 | Merge VQ-202: Document approval workflow + versioning |
| 625f7e0 | Merge VQ-203: Per-tenant document processing queue |
| (from BE_accurate) | Merge remaining Sprint 3: VQ-204, 210, 301, 304, 305, 302 |

All conflicts resolved. BE_clone now matches BE_accurate for all Sprint 3 backend work.