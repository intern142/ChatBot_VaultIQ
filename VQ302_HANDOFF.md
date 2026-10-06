# VQ-302 handoff — resume from here

## Context

Repo: `C:\Users\Test user 1\ChatBot_VaultIQ`
Branch: `vq-302` (created off `main`, pushed to `origin/vq-302`)
Head: `2d43698` — working tree clean, everything committed and pushed.

Task spec: `C:\Users\Test user 1\Documents\vq302.txt`
Process: 7 gates per AGENTS.md. Gate 5 (code review) and Gate 7 (demo) are
the lead's, not ours. Gates 1-4 and 6 are ours.

## What is done

1. **Migration reconciliation (the blocking work, complete).** Four Sprint 3
   branches each declared a migration directly on `006_sessions_tenant_nullable`,
   so `alembic upgrade head` had four targets and no single head. Merged all four
   into `vq-302`: `vq-202`, `vq-301` (which carries VQ-201's migrations),
   `vq-305`, `vq-204`.

   `alembic/versions/012_merge_sprint3_heads.py` collapses the four heads into
   one. It creates nothing; the value is entirely in `down_revision`.

   Verified:
   - `alembic heads` -> `012_merge_sprint3_heads` (single head)
   - `upgrade head` from an empty schema -> all 20 migrations clean
   - `downgrade 006_sessions_tenant_nullable` -> all four branches unwind
   - `upgrade head` -> back to head; `answers`, `answer_feedback`,
     `document_chunks`, `indexing_jobs`, `reset_codes`, `documents`,
     `audit_logs` all present

   Note: `008_platform_access_superadmin` (vq-202) and
   `009_platform_access_backport` (vq-301) are the same Known Defect #2 fix
   carried twice. Both do `DROP POLICY IF EXISTS` before `CREATE POLICY`, so
   they are mutually idempotent. End state is one policy.

2. **Two merge regressions fixed:**
   - `app/routes/auth.py:269` lost indentation in a conflict resolution, module
     would not import.
   - `app/schemas/document.py` took vq-201's `from typing import Literal`
     header with vq-202's body which uses `Optional`.

3. **Upload endpoint combined.** `app/routes/documents.py` upload now carries
   VQ-201's `category`, content-based MIME detection, extraction, quota and
   rollback-on-failure, *plus* VQ-202's `document_group_id`, `version_number`,
   `supersedes_id`, `status="pending"`. Kept `require_roles_with_tenant("client_admin")`
   from VQ-201 (employees cannot upload, AC5) over VQ-202's older
   `("client_admin", "employee")`.

4. **357 tests collect with zero import errors.**

## CRITICAL — how to run the suite

Docker `vaultiq-db` is on port **5433**. `tests/conftest.py` defaults to **5432**.
Always set these or every test errors with `InvalidPasswordError`:

```powershell
$env:ADMIN_DATABASE_URL="postgresql+asyncpg://vaultiq:vaultiq_secret@localhost:5433/vaultiq"
$env:APP_DATABASE_URL="postgresql+asyncpg://vaultiq_app:vaultiq_secret@localhost:5433/vaultiq"
$env:DATABASE_URL_SYNC="postgresql://vaultiq:vaultiq_secret@localhost:5433/vaultiq"
python -m pytest tests/ -q --tb=line
```

## Use the fast static check, not the suite, to catch import errors

Three suite runs were wasted finding two one-line problems. Do this first — it
takes ~15 seconds and catches what `ast.parse` cannot:

```powershell
python -c "
import pathlib
bad=[]
for p in list(pathlib.Path('app').rglob('*.py'))+list(pathlib.Path('tests').rglob('*.py'))+list(pathlib.Path('alembic').rglob('*.py')):
    try: compile(p.read_text(encoding='utf-8'),str(p),'exec')
    except SyntaxError as e: bad.append(f'{p}:{e.lineno} {e.msg}')
print('COMPILE ERRORS:',len(bad))
for b in bad: print(' ',b)
"
python -m pytest tests/ --collect-only -q
```

**`compile()`, not `ast.parse()`.** `ast.parse` does not catch `return` outside
a function — that is a symtable check done by `compile()`. This is exactly the
class of error that cost three runs.

## Immediate next step

**Run the suite once with the env vars above and get the true baseline.** The
earlier "42 failed / 232 errors" was entirely a port mismatch, not real signal.
The true failure count is unknown.

Fix whatever is red. Known suspects for cross-branch regressions:
- `documents` upload/list/preview now go through VQ-201's extraction path
- VQ-202 test fixtures vs VQ-301 fixtures in `tests/test_tenant_lifecycle.py`
  (resolved by taking the vq-202 version — it uses the RLS-enforced
  `app_db_conn` fixture; the vq-301 version had fallen back to `db_conn`)
- two `app/models/__init__.py` and `app/main.py` router lists
- `ROLE_MATRIX` and `tests/isolation_manifest.py` are both hand-merged; the
  route coverage guard (`test_route_coverage_guard`) will catch omissions

## Then: build the actual VQ-302 feature (0% started)

Read `C:\Users\Test user 1\Documents\vq302.txt` for the ACs. Summary:

**Overview figures** — questions/day last 30 days, active users,
answered/partial/not-found split, average confidence.

**Four lists**, each with server-side paging + filtering + search:
- documents (with approval `status` from vq-202 AND `extraction_status` from
  vq-201 — the spec says "state and processing status")
- users
- audit entries
- feedback

**Knowledge gaps** — most frequent not-found and low-confidence questions,
grouped by similarity, with counts and last-asked. `document_chunks.embedding`
(vq-204, pgvector) is the similarity source; `answers` + `answers.confidence`
(vq-305) are the data.

**CSV export of each list** — capped, streamed, safe in a spreadsheet, audited.
"Cannot execute formulas" means CSV injection defence: prefix cells beginning
`= + - @ TAB CR` (or prefix with `'`), and decide/record the policy explicitly.

**Hard constraint:** every figure and list restricted to the requesting tenant,
**including aggregate counts**. RLS is already correct on every source table;
the risk is writing an aggregate query without tenant context, and a `GROUP BY`
that spans partitions. Prefer aggregate-over-`WHERE tenant_id = :t` under RLS
over any application-side filtering.

### Likely file layout
- `app/schemas/dashboard.py` — new
- `app/routes/dashboard.py` — new, register in `app/main.py`
- `app/auth/permissions.py` — add entries; **client_admin only**, super_admin
  DENIED (consistent with documents/search/feedback)
- `tests/isolation_manifest.py` — **must** add every new route or
  `test_route_coverage_guard` fails
- `tests/test_dashboard.py` — new

### Must-proven from the spec
- Every dashboard operation covered by the isolation suite
- Automated tests that aggregates exclude other tenants
- Automated tests that CSV cells cannot execute formulas
- Live container: dashboard figures for tenant A vs direct DB counts

## Known issues inherited from other branches (do not assume they are correct)

- **VQ-305** (`GET /answers/{answer_id}/feedback`): uses
  `scalar_one_or_none()` but the spec says a Client Admin sees *all* feedback
  for an answer. With 2+ voters this raises `MultipleResultsFound`. Broken.
- **VQ-305**: nothing in the app creates `Answer` rows — no answer-selection
  endpoint exists yet. Live evidence was produced by inserting rows directly
  via psql. VQ-302's aggregates will read whatever exists.
- **VQ-204**: Gate 6 used 60 chunks per tenant, not the 5k the spec implies.
  No ADS migration script exists despite `AGENTS.md` claiming one does.
- **VQ-204**: FastEmbed downloads the model from Hugging Face at runtime, which
  contradicts the "no internet, artefacts bundled at build time" rule.
- **VQ-304 / vq-210-tenant-cache / vq-203** exist but were **not** merged.
  vq-304 may also add an `answers`-adjacent table — check before finalising the
  model.
- VQ-202 migration `008_platform_access_superadmin` comment says "offboarding
  (purge) is VQ-302". That refers to a different VQ-302 in an older numbering.
  The spec we are implementing is Client Admin dashboard data. Ignore the
  comment; do not build a tenant purge.
- Four stray helper scripts were committed on `vq-305`
  (`fix_passwords.py`, `fix_hash2.py`, `check_hash.py`, `fix_admin_hash.py`) —
  candidates for removal.
- `AGENTS.md` currently claims Gates 1-6 ✅ for both VQ-204 and VQ-305. That is
  not accurate. Correct it when updating docs.

## Gate discipline

- Gate 1 approach note before more code: write `APPROACH_VQ302.md`.
- Gate 3: paste the real command and real output. No invented numbers.
- Gate 4: walk each AC one by one, confirm, then update `AGENTS.md`.
- Gate 6: live container, real curl/pytest output. Not "tests pass".
- Commit small, story ID in every message, push daily.
