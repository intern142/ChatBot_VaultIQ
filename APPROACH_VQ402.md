# VQ-402 Approach Note — Audit trail, compliance export, retention

**Branch:** `vq-402` (cut from `main`) · **Depends on:** VQ-301 · **Story dates:** 8–9 Oct

## Objective

Everything that happens in a tenant is traceable, exportable, and kept only as long
as that tenant's policy says.

## Current State (recon summary)

- `audit_logs` exists (migration 004) with FORCE RLS, grants `SELECT, INSERT` to
  `vaultiq_app` (the production app identity). No UPDATE/DELETE grant exists today.
- The write helper `write_audit_log()` lives privately in `app/routes/admin.py`;
  only **5 actions** are audited: `create_tenant`, `suspend_tenant`,
  `reactivate_tenant`, `create_invite`, `accept_invite`.
- **Not audited:** login, logout, failed login, upload, delete, export.
- **No export endpoint** (only `GET /admin/tenants/{id}/audit`, super_admin, 500-row JSON).
- **No `retention_days`**, **no conversations/messages tables**, **no job scheduler**.
- Audit read is super_admin-only — a Client Admin cannot see their own tenant's trail.

## Scope vs. Acceptance Criteria — what exists on this branch

AC1 lists events, several of which belong to features that are **not on `main`**
(they live on other story branches). Decisions:

| AC event | Status on `main` | VQ-402 action |
|---|---|---|
| login | endpoint exists | audit `login` (tenant users) |
| logout | endpoint exists | audit `logout` |
| failed login | endpoint exists | audit `failed_login` with reason |
| invite | already audited | keep `create_invite` / `accept_invite` |
| upload | endpoint exists | audit `upload_document` |
| delete | endpoint exists | audit `delete_document` |
| export | **this story** | new endpoint, audits `export_audit` |
| tenant status changes | already audited | keep `suspend_tenant` / `reactivate_tenant` |
| settings change (`retention_days`) | **this story** | recorded inside `create_tenant` details |
| role change | no endpoint exists | action name reserved; wired when the endpoint lands |
| approve / reject | VQ-202 branch, not on main | reserved; wired when approval lands |
| question + docs used + confidence | search/QA is VQ-208 branch, not on main | reserved (`question_answer`); wired when QA lands |

The audit **service** is the single extension point: any future story calls
`write_audit_log()` and its action appears in the trail automatically.

### Scope decisions that need reviewer eyes

1. **Super Admin has no home in the trail.** `audit_logs.tenant_id` is `NOT NULL`
   (per-tenant table, RLS-per-tenant). A super_admin login/logout has no tenant to
   attribute to, so platform-only auth events are **not recorded**. Super Admin
   *actions on tenants* (create/suspend/invite) are already recorded, with
   `actor_user_id` = the super admin. Alternative would be nullable-tenant audit
   rows, which would break the "every audit row belongs to exactly one tenant"
   model and create cross-tenant read questions — rejected.
2. **Failed login with an unresolvable organisation code** (org code doesn't exist)
   has no tenant to attribute to → not recorded. Failed logins where the org code
   resolves (wrong password, locked account, unknown email for a known org, suspended
   tenant) **are** recorded under that tenant with a `reason` in `details`.
   This does not weaken AC2 of VQ-105 (uniform external response): the audit row is
   internal, tenant-scoped, never returned to the caller.
3. **Nightly schedule** — the repo has no scheduler (no celery/apscheduler/cron).
   Retention ships as `python -m app.retention`, intended to be invoked by the
   platform's cron/entrypoint at night (documented in the module docstring). Tests
   call `run_retention_once()` directly. No new dependency is added (no-internet rule).
4. **Fail-closed:** if the audit insert fails, the request fails. A compliance trail
   that silently skips entries is worse than a 500.

## Design

### 1. Shared audit service — `app/services/audit.py`

`write_audit_log(db, tenant_id, actor_user_id, actor_role, action, target_type,
target_id, details)` moves out of `routes/admin.py` unchanged in signature, plus it
now **sets the tenant context itself** (SET LOCAL, RLS-safe under `vaultiq_app`) so
callers cannot forget it. `admin.py` and `invite.py` import it; auth and documents
routes use it too.

Wiring:

- `login` → target_type `user`, target_id user.id, details `{organisation_code}`
- `failed_login` → target_type `user`, target_id user.id (or tenant.id for
  unknown-email), details `{reason}`
- `logout` → target_type `session`, target_id session.id
- `upload_document` / `delete_document` → target_type `document`, details with
  filename/mime/size (customer-visible metadata; the trail is tenant-scoped so this
  is fine — platform operators still never see it)
- `export_audit` → target_type `audit_export`, target_id tenant.id, details
  `{start_date, end_date, format}`

### 2. Migration `007_audit_retention`

- `tenants.retention_days INTEGER NOT NULL DEFAULT 365 CHECK (retention_days >= 1)`
  → per-tenant retention policy, settable at tenant creation.
- **Explicit `REVOKE UPDATE, DELETE ON audit_logs FROM vaultiq_app`** — makes AC2 a
  database-level guarantee for the application identity, independent of RLS, and
  guards against a future `GRANT ALL`. (Grants today are already SELECT+INSERT only;
  the REVOKE documents and locks the intent.)
- Function **`vaultiq_purge_tenant_retention(p_tenant_id uuid)`** —
  `SECURITY DEFINER`, owned by the migration role (`vaultiq`, BYPASSRLS so FORCE RLS
  doesn't block the purge), `search_path` pinned, `EXECUTE` revoked from `PUBLIC`
  and granted to `vaultiq_app` only.
  - Reads that tenant's own `retention_days`, computes
    `cutoff = now() - retention_days days`, deletes **only**
    `WHERE tenant_id = p_tenant_id AND created_at < cutoff`.
  - Purges `audit_logs`; also purges `conversations`/`messages` **if those tables
    exist** (`to_regclass` guard) with the same tenant+cutoff predicate — so the AC
    "conversations … removed nightly" holds as soon as the QA story merges its tables.
  - Returns per-table row counts. The caller cannot pass a cutoff — the tenant's own
    policy is the only input, which is what makes "never across tenants" structural:
    the function is single-tenant by construction.
- Downgrade drops the function and the column.

Why a DB function instead of app-side `DELETE`: the app identity physically cannot
DELETE audit rows (no grant), so the only lawful delete path is this function, which
is scoped to one tenant and rows older than that tenant's own policy.

### 3. Export endpoint — `GET /audit/export` (new `app/routes/audit.py`)

- `require_roles_with_tenant("client_admin")` — AC3 says Client Admin; employee 403,
  super_admin 403 (no tenant to export for via this path; super_admin keeps the
  existing `GET /admin/tenants/{id}/audit`).
- Tenant comes **only from the token** — no tenant id in path or query, so there is
  no cross-tenant parameter to tamper with.
- Query params: `start_date`, `end_date` (ISO dates, optional; inclusive range,
  `end_date` covers the whole day), `format` = `csv` (default) | `json`.
  `start_date > end_date` → 400.
- **The export itself is recorded first** (`export_audit`), then rows are read, so
  the returned file contains its own export entry — a compliance export is
  self-including and the request is on the trail even if generation fails after it.
- CSV columns: `id, created_at, actor_user_id, actor_role, action, target_type,
  target_id, details, tenant_id`; `details` JSON-serialized; proper CSV escaping via
  the stdlib `csv` module; served as `text/csv` attachment.
- Isolation: explicit `WHERE tenant_id = :token_tenant` **and** RLS tenant context.

### 4. Retention job — `app/retention.py`

- `run_retention_once()` — connects with the app DB identity, selects all tenants
  (`vaultiq_app` has SELECT on `tenants`), calls `vaultiq_purge_tenant_retention`
  **once per tenant**, prints per-tenant counts. Never a single statement spanning
  tenants.
- Entry point `python -m app.retention`; nightly invocation documented as
  `0 3 * * * python -m app.retention` (platform cron — outside the container's
  network boundary, no new deps).

### 5. Lockstep updates required by existing guards

- `app/auth/permissions.py` ROLE_MATRIX → `("GET", "/audit/export"): {"client_admin"}`
  (else `test_all_endpoints_have_permissions_declared` fails).
- `tests/isolation_manifest.py` → add `("GET", "/audit/export")`; add `"/audit"` to
  the coverage-guard prefix tuple in `tests/test_isolation_suite.py`.
- `PERMISSIONS.md` → document the new operation.
- `app/schemas/tenant.py` / `app/models/tenant.py` → `retention_days` on
  TenantCreate (default 365) / TenantResponse / TenantListResponse.

## Tests (Gate 3) — new `tests/test_audit_retention.py`

Must-proven items from the story are tests 1–2:

1. **Application identity cannot modify audit rows** — connect as `vaultiq_app`
   (`app_db_conn` fixture, same pattern as `test_rls.py`): `UPDATE` and `DELETE` on
   `audit_logs` both raise `InsufficientPrivilege`; `INSERT`/`SELECT` with tenant
   context still work. (Targets the production app identity directly — independent of
   the Known Defect that the HTTP suite runs as the `vaultiq` superuser.)
2. **Retention only touches one tenant** — seed old + recent rows for tenants A and B,
   run the purge for A: A's old rows gone, A's recent rows kept, **all** of B's rows
   kept. Same test repeated through `run_retention_once()` (job path).
3. Ten actions performed via HTTP → export contains all ten (automated twin of the
   live evidence).
4. Export records itself (`export_audit` present in its own output).
5. Export date-range filtering; `start > end` → 400.
6. Export: employee → 403, super_admin → 403, unauthenticated → 401.
7. Cross-tenant: tenant A's export contains zero tenant B identifiers.
8. Login / failed login / logout / upload / delete each produce their audit row.
9. No write method exists on audit routes (no API path to edit/delete trail rows).
10. `retention_days` defaults to 365 and is honoured by the purge.
11. Existing guards stay green: permissions router-walk, isolation coverage guard
    (extended to `/audit`), full suite.

## Live container evidence (Gate 6)

Against `uvicorn app.main:app` + Docker PG: perform 10 distinct tenant actions
(login, failed login, upload, download, delete, logout, invite create, invite
accept, tenant suspend, export), then export the range and show all 10 present in
the file; plus the `vaultiq_app` UPDATE/DELETE refusal and a retention run showing
one tenant purged and the other untouched.

## What Could Go Wrong

| Risk | Mitigation |
|---|---|
| Audit write breaks an endpoint's happy path | Fail-closed by design; full suite proves every path still 2xx |
| Forgetting tenant context on an audit insert (RLS) | Service sets context itself |
| Retention job purges across tenants | Purge function is single-tenant by construction; test 2 proves B untouched |
| New `/audit` route added later without isolation coverage | `/audit` added to coverage-guard prefixes |
| Export leaks another tenant's rows | Token-derived tenant + explicit WHERE + RLS + leak test 7 |
| Super-admin auth events missing from trail | Documented scope decision above (reviewer to confirm) |

## Gates

1. **Gate 1** — this note
2. **Gate 2** — implement on `vq-402`, small commits, story ID in each message
3. **Gate 3** — tests written, full suite green, paste run summary
4. **Gate 4** — self-review against ACs, then PR
5. **Gate 5** — code review
6. **Gate 6** — live container evidence (10 actions → export contains all 10)
7. **Gate 7** — demo Friday
