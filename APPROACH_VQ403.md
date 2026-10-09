# APPROACH_VQ403 — Tenant offboarding and full purge

**Story:** VQ-403 · Track: Backend · Branch: `vq-403` (cut from `main` @ `161eb6f`)
**Status:** ⏳ Awaiting Gate 1 approval — no code until "approved"
**Spec:** `C:\Users\Test user 1\Documents\vq403.txt` (copied into `STATE.md`)

---

## 1. Acceptance criteria (restated)

1. Super Admin can offboard a tenant **after re-confirming their own identity**;
   the tenant is locked immediately and all its sessions end.
2. A **7-day grace period** during which offboarding can be cancelled.
3. After grace, **everything** is removed: every record, derived search
   artefact, file, cached answer, pending job, and the tenant's index space.
4. **Backups containing the tenant are flagged** so they expire per policy.
5. A **deletion report** — what was removed, how much, when, by whom — is
   produced and stored **outside the tenant**.

**Must be proven:** (a) automated test: after purge, zero records and zero files
reference the tenant and other tenants are untouched; (b) staging evidence: a
purged tenant, DB + disk searched for its identity, and the deletion report.

## 2. Scope

**In:** two tenant lifecycle endpoints + two report endpoints, grace-period
state machine (+ columns), SECURITY DEFINER purge function, purge CLI
(`python -m app.offboard_purge`), storage wipe, deletion-report table,
ROLE_MATRIX/manifest updates, tests.

**Out:** backup expiry execution (no backup infra in repo — we provide the
flag, §3.5), MFA (doesn't exist — re-confirm = password, §3.1), email
notifications (no mail system), frontend, pgvector index space (doesn't exist
yet — guarded placeholder, §3.3), VQ-402 features (they live on `vq-402`,
integration plan §4).

## 3. Design

### 3.1 State machine + identity re-confirm

```
active ──┐                        ┌──► active        (cancel, within grace)
suspended ┼─► offboarding ────────┤
          │   (grace = 7 days)    └──► purged        (purge job, after grace)
          └─► purged              (already-purged: all writes → 409)
```

- Migration adds to `tenants`: `offboarded_at`, `offboarded_by (FK users,
  ON DELETE SET NULL)`, `purge_after` (= offboarded_at + 7 days, constant
  grace — no config column), `purged_at`.
- **Immediate lock is already enforced** on this branch: login
  (`app/routes/auth.py:79`) and the request dependency
  (`app/auth/dependencies.py:120`) both refuse `suspended`/`offboarding`
  tenants today. Offboarding therefore inherits the lock for free; we still
  revoke ALL sessions explicitly at offboard time, mirroring `suspend_tenant`.
- **Re-confirm identity:** body `{"password": "..."}`, verified with
  `verify_password` against the *acting super admin's own* hash (they are
  already JWT-authenticated; this is a step-up check, not a login). Wrong
  password → `403 "Identity re-confirmation failed"` (generic, no detail).

### 3.2 Endpoints (all `super_admin` only, via ROLE_MATRIX)

| # | Endpoint | Behaviour |
|---|----------|-----------|
| 1 | `PATCH /admin/tenants/{id}/offboard` | re-confirm password → status `offboarding`, set `offboarded_at/by/purge_after`, revoke ALL sessions, audit `offboard_tenant`. Guards: `purged` → 409; already `offboarding` → 409. Allowed from `active` or `suspended`. |
| 2 | `PATCH /admin/tenants/{id}/cancel-offboarding` | only from `offboarding` → `active`, clear offboard fields, audit `cancel_offboarding`. From `active`/`suspended` → 409; from `purged` → 409 (too late by definition). |
| 3 | `GET /admin/deletion-reports` | list all reports (platform-level, newest first, paginated like `/documents`). |
| 4 | `GET /admin/deletion-reports/{id}` | single report body. |

**Purge has no endpoint.** Grace cannot be bypassed by any API call; purge
runs only from the CLI below. Naming follows VQ-107's
`PATCH …/suspend` / `…/reactivate` pattern.

### 3.3 Purge mechanics — two layers, fail-closed, idempotent

**Migration `007_offboarding`** (see §4 for the head-collision plan) also adds
table `deletion_reports`:
`id, tenant_id (FK — tombstone tenant persists), short_code, name,
initiated_by, initiated_at, purge_after, purged_at, grace_days,
report (JSONB), backup_flag (JSONB), created_at`.
**No RLS** (platform-level, lives outside the tenant's reach): `GRANT SELECT
TO vaultiq_super_admin`; **no grant to `vaultiq_app`**. Super-admin API reads
follow the same dev-superuser path as every other super-admin endpoint today
(Known Defect #2 — unchanged, noted).

**Layer 1 — SQL function `purge_tenant(uuid) RETURNS jsonb`, SECURITY DEFINER:**
- **Validates inside the function:** `status = 'offboarding' AND purge_after
  <= now()` else `RAISE` — even a compromised app session cannot purge early.
  This validation is the reason the function may be granted to `vaultiq_app`.
- Deletes in FK-safe order (audit_logs → invites → sessions → documents →
  users), returning per-table row counts.
- **Derived artefacts via `to_regclass` guards** (same pattern as VQ-402's
  retention function — tables that don't exist yet are skipped, tables that
  arrive later are covered): `text_chunks, embeddings, document_versions,
  conversations, messages, feedback, cached_answers, ingestion_jobs` (+ any
  added to the guard list before impl). Vector **index space**: rows deleted
  ⇒ index entries freed; physical reclaim is VACUUM's job (ops follow-up,
  noted in report field `vacuum_recommended: true`).
- **`audit_logs` rows are purged too** — "every record" means every record.
  The offboard/cancel events live only during grace; after purge the
  *deletion report* (outside the tenant) is the surviving who/when evidence.
  This keeps the must-prove invariant literal: **zero rows in any
  tenant-scoped table, exactly one platform row in `deletion_reports`.**
- Single transaction — all-or-nothing on any FK/constraint error.
- `GRANT EXECUTE TO vaultiq_app`. The function is the **only lawful delete
  path for audit rows** (VQ-402's REVOKE blocks app `DELETE`; owner-definer
  path mirrors the retention-function precedent — on this branch the REVOKEs
  don't exist yet, but the structure stays so the branches converge).

**Layer 2 — CLI `python -m app/offboard_purge` (mirrors `app/retention.py`,
intended daily, runs as `vaultiq`):**
1. Find tenants with `status='offboarding' AND purge_after <= now()`.
2. Call `purge_tenant(id)` → row counts.
3. Measure disk usage of `storage/{tenant_id}/**`, then `shutil.rmtree`
   (files can't be deleted by SQL). Missing dir = fine (idempotent).
4. Insert `deletion_reports` row (counts + bytes + backup flag).
5. Set `status='purged', purged_at=now()`.
6. Status flips to `purged` **only after storage wipe succeeds** — a failed
   wipe leaves the tenant `offboarding`; rerun completes it. Function tolerates
   already-zero tables ⇒ job is safely re-runnable.

**Cancellation vs. purge race:** cancel is allowed while `status='offboarding'`
even if grace just expired; whoever commits first wins — purge re-validates
inside its transaction, so no double-state is possible.

### 3.4 What each AC maps to

| AC | Mechanism |
|----|-----------|
| 1 re-confirm + lock + sessions end | endpoint #1 (password step-up) + explicit session revoke + existing lock checks |
| 2 7-day cancellable grace | `purge_after` column + endpoint #2 + purge validates |
| 3 total removal | SQL function (records, derived, jobs) + rmtree (files) + guard list (index space) |
| 4 backups flagged | `deletion_reports.backup_flag = {"state": "eligible_for_expiry", "flagged_at": purged_at}` — a **durable flag recorded at purge time**; no backup system exists inside the repo, so expiry execution is out-of-repo and keyed off this record. Documented honestly in the report. |
| 5 deletion report outside tenant | `deletion_reports` table: no tenant scoping, no RLS, super-admin-only grant |

### 3.5 Tests (Gate 3 plan) — new `tests/test_offboarding.py`

- **Identity:** wrong password → 403, no state change; correct → status +
  `offboarded_by` set + sessions revoked + login refused + audit row.
- **Roles:** `client_admin` / `employee` → 403 on all four endpoints
  (ROLE_MATRIX entries + manifest/coverage guard).
- **Grace:** cancel → back to `active`, login works again; cancel from
  `active`/`suspended`/`purged` → 409; offboard from `purged` → 409.
- **Purge early:** function raises before grace → CLI no-op → zero deletes.
- **Purge after grace** (backdate `purge_after` via SQL as test superuser):
  **must-prove test** — every tenant-scoped table queried for tenant B's id →
  0 rows; `storage/{id}` absent; tenant A's row counts + files byte-identical
  before/after; report row exists with counts matching the deleted reality;
  `client_admin` cannot see the report, `super_admin` can.
- **Idempotency:** running the CLI twice → second run no-op, no error.
- Existing suite stays green (baseline recorded at Gate 3 on this branch).

## 4. Branch & integration plan (this branch is `main`-based by user instruction)

- **VQ-402 is NOT on this branch.** Offboarding audit uses the local
  `write_audit_log` in `app/routes/admin.py:42` (exists on `main`,
  writes `audit_logs` which exists). After PR #16 merges: rebase, switch
  imports to `app/services/audit.py`, pick up REVOKEs + retention function.
- **Dual alembic heads:** this branch adds `007_offboarding` (down_revision
  `006`); VQ-402 has `007_audit_retention` (also down `006`). Integration
  fix (not a blocker for this story): if VQ-402 merges first → re-parent
  `007_offboarding` onto it; otherwise add a merge migration (precedent:
  `a1340d9f596a_merge_…`).
- Ticket dependency "Depends on: VQ-402 ⏳" is satisfied at *integration*,
  not at branch time — recorded here as the deliberate decision.

## 5. What could go wrong

- **FK order bug** mid-purge → whole purge in one transaction, fails closed,
  tenant stays `offboarding`, rerun after fix.
- **Premature purge** → prevented by validation inside the SECURITY DEFINER
  function, not in app code.
- **`rmtree` partial failure** → status not flipped until wipe completes;
  idempotent rerun.
- **"Zero records" test vs. platform artifacts** → resolved by design (§3.3):
  the report is the only survivor and is deliberately outside tenant scope.
- **Super-admin endpoints under `vaultiq_app`** → Known Defect #2, pre-existing,
  Gate 6 evidence via dev superuser (same as VQ-402).

## 6. Commit plan (Gate 2)

Small commits, `VQ-403:` prefix: ① migration + models + schemas → ② endpoints +
ROLE_MATRIX → ③ purge function + CLI + storage wipe → ④ report endpoints →
⑤ tests → ⑥ manifest/coverage updates. Push daily; no code before Gate 1
approval.
