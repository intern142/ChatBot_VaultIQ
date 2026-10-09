# VQ403 Self-Review (Gate 4)

Story: VQ-403 — Tenant offboarding and full purge · Branch: `vq-403`
Method: acceptance criteria walked one by one against the implementation and tests.

---

## AC1 — Super Admin offboards after re-confirming identity; locked immediately; all sessions end

| Check | Where | Status |
|---|---|---|
| Endpoint exists, super_admin only (router dependency + ROLE_MATRIX) | `app/routes/admin.py:offboard_tenant`, `app/auth/permissions.py` | ✅ |
| Body requires password; verified against the *acting* super admin's own hash | `verify_password(request.password, current_user.password_hash)` | ✅ |
| Wrong password → 403, **no state change** (status/sessions/audit untouched) | `test_offboard_wrong_password_rejected` | ✅ |
| Immediate lock: login refused for offboarding tenant | pre-existing `auth.py:79`; asserted in `test_offboard_happy_path` | ✅ |
| Immediate lock: all API requests (non-logout) refused | pre-existing `dependencies.py:120` | ✅ |
| All sessions end | explicit `DELETE sessions WHERE tenant_id` at offboard; asserted `count = 0` | ✅ |
| Audit entry `offboard_tenant` written | `write_audit_log` (admin.py helper); asserted `count = 1` | ✅ |
| Conflict guards: already offboarding → 409, purged → 409, unknown → 404, from suspended → allowed | `TestOffboard` (4 tests) | ✅ |

## AC2 — 7-day grace period, cancellable

| Check | Where | Status |
|---|---|---|
| `purge_after = offboarded_at + 7 days` at offboard | `OFFBOARD_GRACE_DAYS = 7`; asserted 6.9–7.1d window | ✅ |
| Cancel → back to active, offboard fields cleared, audit written | `cancel_offboarding`; `test_cancel_restores_tenant` | ✅ |
| After cancel, login works again | asserted in same test (200) | ✅ |
| Cancel guards: active/suspended/purged → 409, unknown → 404 | `TestCancelOffboarding` (3 tests) | ✅ |
| Purge impossible during grace — validation lives **inside** the SQL function, not app code | `purge_tenant` RAISEs; `test_function_refuses_early_purge` + `test_purge_before_grace_is_noop` | ✅ |
| No API endpoint can trigger a purge at all (grace unbreakable by design) | purge runs only via `python -m app.offboard_purge` | ✅ |

## AC3 — After grace, everything removed: records, derived artefacts, files, cached answers, jobs, index space

| Check | Where | Status |
|---|---|---|
| Every record: audit_logs, invites, sessions, documents, users | `purge_tenant` FK-safe loop; must-prove test asserts **0 rows in all five** | ✅ |
| Derived artefacts (chunks, embeddings, versions, conversations, messages, feedback) | `to_regclass` + `tenant_id`-column guard list (8 tables) | ✅ |
| Guard branch actually purges when the table exists **and skips when it has no tenant_id** | `test_guarded_derived_tables_purged_skipped_when_unsafe` (created/dropped real `text_chunks` + `cached_answers`) | ✅ |
| Cached answers / pending jobs / index space | `cached_answers`, `ingestion_jobs` in guard list; index entries freed by row deletion, `vacuum_recommended: true` recorded in report (no vector index exists on this branch yet) | ✅ |
| Files | `purge_tenant_storage` rmtree; must-prove asserts tenant A dir gone | ✅ |
| Single transaction — all-or-nothing; status flips to `purged` only after wipe succeeds; rerun safe | CLI structure + `test_purge_before_grace_is_noop`/second-run assertion in must-prove | ✅ |
| **Must-prove automated test** (zero records + zero files for A, B byte-identical) | `test_must_prove_total_purge_and_other_tenant_untouched` | ✅ |

## AC4 — Backups flagged so they expire per policy

| Check | Where | Status |
|---|---|---|
| Durable flag written at purge: `{"state": "eligible_for_expiry", "flagged_at": …}` | `deletion_reports.backup_flag`; asserted in must-prove + smoke test | ✅ |
| Honest scope: no backup system exists inside the repo → we record the flag; expiry execution is out-of-repo, keyed off the report | APPROACH_VQ403.md §3.4 (agreed in Gate 1) | ✅ |

## AC5 — Deletion report: what / how much / when / by whom — stored outside the tenant

| Check | Where | Status |
|---|---|---|
| What: per-table `rows_deleted` counts (incl. guarded derived tables) | report JSONB; asserted `users=2, invites=1, documents=1…` | ✅ |
| How much: `files_deleted`, `bytes_deleted` | asserted `>= 1` / `> 0` | ✅ |
| When: `purged_at`, `initiated_at`, `flagged_at` | asserted non-null; `grace_days = 7` | ✅ |
| By whom: `initiated_by` = offboarding super admin | asserted non-null | ✅ |
| Stored **outside** tenant: no RLS, no `vaultiq_app` grant, super_admin SELECT only, survives the purge (FK → tombstone tenant row) | migration `007_offboarding`; `DeletionReport` model | ✅ |
| Super admin reads via API; client_admin **and** employee get 403 | `test_must_prove…` + `TestRoleGuards` | ✅ |
| Unknown report id → 404 | `test_report_404_unknown_id` | ✅ |

## Cross-cutting checks

- **Route coverage guard + router-walk (ROLE_MATRIX)**: all 4 new endpoints declared — 22/22 guard tests pass.
- **Full suite**: `python -m pytest tests/ -q` → **154 passed** (137 baseline on this branch + 17 → 18 later; final run recorded in STATE.md), 329s, on fresh `vaultiq_vq403`.
- **Migration**: fresh `alembic upgrade head` 001→007 clean; `downgrade 006` + `upgrade head` roundtrip clean.
- **CLI smoke (outside pytest)**: early-purge refused, full purge, zero records, storage wiped, report + flag, not-due tenant untouched, idempotent re-run — all OK (`%TEMP%\opencode\vq403_purge_smoke.py`).
- **Fail-closed**: grace check inside SECURITY DEFINER function (app code cannot bypass); purge transaction rolls back on any failure; `status='purged'` only after storage wipe.
- **Rule 4 (operators see no customer content)**: report holds counts/metadata only — no document text, no chunk content.
- **Known deviation from repo style, deliberate**: new endpoints use **409** for state conflicts where VQ-107 used 400 — APPROACH_VQ403.md specified 409 and was the approved contract.
- **VQ-402 integration**: audit written via `admin.py` local helper (VQ-402's `services/audit.py` absent on this branch by design); `007_offboarding` head-collision with VQ-402's `007_audit_retention` documented in APPROACH_VQ403.md §4 — resolved at rebase/merge time.

## Verdict

All five acceptance criteria and both must-prove requirements are implemented and
covered by tests on the running database. Ready for Gate 5 (code review).
