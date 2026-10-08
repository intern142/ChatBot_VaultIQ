# VQ-402 Gate 4 — Self-Review

**Branch:** `vq-402`
**Commits:** `b4ba223` (Gate 1 approach note), `90a6b0b` (Gates 2-3 implementation + tests)

## Acceptance Criteria — walked one by one

### 1. Recorded: login, logout, failed login, invite, role change, upload, approve, reject, delete, every question with which documents were used and the confidence, exports, settings changes, tenant status changes — PARTIAL, by scope

- All audit writes go through one helper, `app/services/audit.py::write_audit_log`.
  It is called inside the same DB transaction as the action itself (fail-closed:
  if the audit insert fails, the action fails).
- **Recorded today — 11 action names:** `login`, `logout`, `failed_login`
  (with reason: wrong_password / unknown_email / account_locked /
  tenant_suspended), `create_invite`, `accept_invite`, `upload_document`,
  `delete_document`, `create_tenant` (retention_days included in details),
  `suspend_tenant`, `reactivate_tenant`, `export_audit`.
- **Reserved for stories not yet on `main`** (documented in
  `APPROACH_VQ402.md`): `role_change` (depends on VQ-301, the story this
  ticket depends on), `approve_*`/`reject_*` (document approval, VQ-204),
  `question_asked` with documents used + confidence (search/QA, VQ-210),
  `settings_change` (there is no settings-mutation endpoint on `main` yet).
  Wiring is a one-line call when those features land.
- Super-admin auth events carry no tenant, and the trail is tenant-scoped by
  design — platform-level login events are deliberately not written here.
- Tests: `test_login_logout_and_failed_login_recorded`,
  `test_unknown_email_for_known_org_is_recorded`,
  `test_upload_and_delete_recorded`, `test_export_contains_all_ten_performed_actions`.

### 2. Audit records cannot be edited or deleted by the application; only the retention process removes them — DONE

- Migration `007_audit_retention.py` issues explicit
  `REVOKE UPDATE, DELETE ON audit_logs FROM vaultiq_app` and
  `... FROM vaultiq_super_admin` (grants were already SELECT+INSERT-only;
  the REVOKE locks the intent against any future GRANT).
- The API exposes no mutation surface: only `GET /audit/export` and the
  existing `GET /admin/tenants/{id}/audit`. POST/PATCH/PUT/DELETE on audit
  routes return 405 (`test_no_write_method_exists_on_audit_routes`).
- The only delete path is `vaultiq_purge_tenant_retention(uuid)`,
  SECURITY DEFINER, `EXECUTE` revoked from `PUBLIC`, granted to
  `vaultiq_app` only.
- Tests (run as the real app identity `vaultiq_app`):
  `test_app_identity_cannot_update_audit_rows`,
  `test_app_identity_cannot_delete_specific_audit_row`,
  `test_app_identity_can_insert_and_select_audit_rows`,
  `test_vaultiq_app_holds_only_select_insert_on_audit_logs`.

### 3. Client Admin can export their tenant's audit trail for a date range; the export itself is recorded — DONE

- `GET /audit/export` (`app/routes/audit.py`): `client_admin` only in
  `ROLE_MATRIX` + router dependency; tenant comes only from the token
  (super admin has no tenant → 403); `start_date`/`end_date` validated
  (format + start <= end), `format=csv|json`.
- The `export_audit` row is written **before** the trail rows are read, so
  the export always contains itself.
- Filename embeds the tenant short code + date range; CSV built with the
  stdlib `csv` module (no injection of spreadsheet formulas from the
  newline/comma-safe writer).
- Tests: 9 in `TestAuditExport` + 4 in the isolation suite
  (`test_export_contains_only_own_tenant_rows` — tenant B marker text and
  row id absent from tenant A's export; employee/super-admin denied;
  unauthenticated denied).

### 4. Conversations and audit records older than the tenant's retention period are removed nightly, per tenant, never across tenants — DONE

- `app/retention.py::run_retention_once()` iterates tenants and calls the
  purge function once per tenant, each in its own transaction.
- The function reads **that tenant's own** `retention_days`, sets a
  transaction-local `app.current_tenant`, and deletes only
  `tenant_id = p_tenant_id AND created_at < cutoff`.
- `conversations`/`messages` are purged only if those tables exist and have
  the needed columns (`to_regclass` guard) — the QA story does not exist on
  `main` yet.
- Nightly scheduling: no scheduler infrastructure exists in this repo, so the
  job is a plain CLI (`python -m app.retention`) with the cron line
  `0 3 * * *` documented in `APPROACH_VQ402.md` — same decision pattern as
  prior stories (no new infra, no network).
- Tests: `test_purge_touches_only_the_requested_tenants_old_rows` (direct SQL
  as app identity: A's stale rows die, A's fresh row and **all** of B's rows
  survive), `test_retention_job_purges_per_tenant`,
  `test_retention_job_handles_empty_database`.

## Must Be Proven

| Requirement | Status |
|---|---|
| Automated test: application identity cannot modify audit rows | Done — 4 tests, run as `vaultiq_app` (Gate 3) |
| Automated test: retention only touches one tenant | Done — `test_purge_touches_only_the_requested_tenants_old_rows` (Gate 3) |
| Live container: 10 actions performed, export contains all 10 | **Gate 6 — pending** |

## Gate 3 — Tests green

```
python -m pytest tests/ -q
163 passed, 1 warning in 326.10s
```

163 = 137 (main baseline) + 26 new (22 `test_audit_retention.py` + 4
isolation-suite export tests). Full suite run on DB `vaultiq_vq402`
(migrations 001 → 007, downgrade → upgrade roundtrip verified including the
`ix_audit_logs_tenant_created` index).

## Checklist (relevant items)

- [x] Migration reversible — `alembic downgrade -1` then `upgrade head` verified
- [x] Index on frequently queried columns — `ix_audit_logs_tenant_created (tenant_id, created_at)` (export + nightly purge), mirrors `ix_documents_tenant`
- [x] DB-level constraints — `CHECK (retention_days >= 1)`; grants/REVOKE enforced in the database, not in Python
- [x] Parameterised SQL everywhere (SQLAlchemy ORM + psycopg2 `%s` params); export values escaped by stdlib `csv`
- [x] AuthN/AuthZ — export is `client_admin` only; unauthenticated → 401/403
- [x] Tenant comes only from the verified token; no tenant id accepted from query/body
- [x] Cross-tenant data access blocked — export self-test + isolation suite; response never contains another tenant's id/rows
- [x] Super admin denied (no tenant of their own on this path)
- [x] No secrets, no `print()` in production code
- [x] Negative tests — invalid date range, bad dates, wrong roles, unauthenticated, empty DB
- [x] No new dependencies — stdlib `csv`/`json`, existing psycopg2

## Not committed

Repo-root `debug_*.py`, `_g6_*.py`, `test_db_connection.py` are untracked
scratch from other stories (VQ-207 etc.) — deliberately left out of this PR.
