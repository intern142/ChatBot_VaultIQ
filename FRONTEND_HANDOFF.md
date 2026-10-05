# Frontend handoff — running VaultIQ locally

Written by the backend track. Everything here is verified against the current
backend code on `BE_accurate` / `be_clone` (commit `d90833d`).

---

## 1. Fix your branch base (do this first)

`fe_clone` currently points at `36ffb78`, which is `origin/main`. That commit
does **not** contain the CORS middleware, so every browser request to the API
will be blocked before it reaches the backend.

`be_clone` is correct — it is at `d90833d` and has CORS.

```bash
git checkout fe_clone
git rebase be_clone
```

If the rebase fights with existing work, recreate the branch from `be_clone`.

**Verify before you build anything:**

```bash
git log --oneline -1        # must show d90833d
git log --oneline --all | grep -i cors
```

If `d90833d` is missing, the browser will refuse every API call and it will
look like a backend bug. It is not.

---

## 2. Fix npm / Node

If any `npm` command fails with:

```
Could not determine Node.js install directory
Error: EPERM: operation not permitted, lstat 'C:\Users\<someone>\AppData'
```

then the `nvm4w` symlink is pointing at a user profile that no longer exists.
This is a machine setup problem, not a project problem.

```bash
nvm4w install 24.19.0
node --version
npm --version
```

**Workaround if that does not work** — put the standalone Node ahead of nvm4w
on PATH for your shell:

```powershell
$env:PATH = "C:\Program Files\nodejs;" + (($env:PATH -split ';' | Where-Object { $_ -notlike '*nvm4w*' }) -join ';')
```

Do not commit `node_modules`. If your branch already tracks it, see §8.

---

## 3. Run the backend

```bash
docker ps --filter name=vaultiq-db     # expect Up, 0.0.0.0:5433->5432
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

`DATABASE_URL` must point at **port 5433**, not 5432.

Check it:

```bash
curl http://127.0.0.1:8000/health      # => {"status":"ok"}
```

---

## 4. The four constraints where integrations break

These are the ones that will bite. Everything else is discoverable from the
code; these are not.

### Port 5173, exactly

```ts
server: { port: 5173, strictPort: true }
```

The API's CORS allowlist is *only* `http://localhost:5173` and
`http://127.0.0.1:5173`. On 5174 every request fails. `strictPort` makes the
dev server fail loudly on a clash instead of silently moving ports, which the
browser would then reject as an unlisted origin.

### Routes are `/admin/*`

There is no bare `/tenants` endpoint.

| What you want | Real endpoint |
| --- | --- |
| List tenants | `GET /admin/tenants` |
| Create tenant | `POST /admin/tenants` |
| Suspend | `PATCH /admin/tenants/{id}/suspend` |
| Reactivate | `PATCH /admin/tenants/{id}/reactivate` |
| Invite first admin | `POST /admin/tenants/{id}/invite` |
| Audit trail | `GET /admin/tenants/{id}/audit` |

### PATCH, not POST

Suspend and reactivate are `PATCH`. `POST` returns 404.

### One Bearer token, no refresh token

The backend issues a single access token. There is no refresh token to store,
no expiry timestamp to track, no silent-refresh logic. Store `access_token`
and send it as:

```
Authorization: Bearer <access_token>
```

`/auth/refresh` takes the Bearer header. It does **not** accept
`refresh_token` in a request body.

---

## 5. Auth contract

Request body — note `organisation_code`, not `org_code`:

```json
{ "organisation_code": "ACME", "email": "...", "password": "..." }
```

Use `organisation_code: "SUPER"` for platform accounts.

Response:

```json
{ "access_token": "...", "token_type": "bearer", "role": "client_admin", "tenant_id": "..." }
```

`tenant_id` is `null` for platform accounts.

Endpoints: `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`
(Bearer required for refresh and logout).

There is **no** `/auth/register` and **no** `/auth/verify`. New client admins
are created by accepting an invite at `POST /invite/accept` (public, body is
`code` + `password`).

---

## 6. Documents

| What you want | Real endpoint | Who |
| --- | --- | --- |
| Upload | `POST /documents` | client_admin only |
| List | `GET /documents` | client_admin, employee |
| Usage | `GET /documents/usage` | client_admin |
| Preview | `GET /documents/{id}/preview` | client_admin, employee |
| Download | `GET /documents/{id}/download` | client_admin, employee |
| Delete | `DELETE /documents/{id}` | client_admin |

**Upload is multipart.** Do not set `Content-Type` yourself on that request —
the browser must add the multipart boundary.

**What upload actually supports right now:** 6 formats (pdf, txt, md, docx,
xlsx, csv), 50 MB per file. There is no per-tenant quota, no OCR, and no
category field yet. If your upload screen implies "any file type", that is
not what the backend does.

**Cross-tenant reads return 404, not 403.** That is deliberate — a 403 would
confirm the resource exists.

---

## 7. Two known backend defects — read before you hit them

### Super admin login returns 401 under `vaultiq_app`

`POST /auth/login` with `organisation_code=SUPER` returns **401** when the app
connects as the production database role `vaultiq_app`. The row-level security
policies on `users` and `sessions` have no branch for `tenant_id IS NULL`, and
platform accounts have no tenant, so the row is invisible to the policy.

Running locally as the `vaultiq` superuser, it works. So you may never see
this.

**If you hit a 401 on `SUPER` login, do not work around it in the frontend.**
No CORS change, no retry, no special-case error handling. A fix is being
written on the backend, and any workaround you add will have to be removed
later and may hide the real bug in the meantime.

### No RLS policy has actually been proven to block anything

Every test run and every CI run connects as `vaultiq`, which has
`rolsuper = t` and `rolbypassrls = t`. Under that role every row-level
security policy is inert — it does not execute.

This means the existing test suite proves the *application code* refuses
cross-tenant access. It does **not** prove the *database* refuses it. There is
a migration in progress to close that gap.

Do not describe the demo as proving database-level isolation.

---

## 8. Do not commit `node_modules`

`.gitignore` should cover:

```
node_modules/
dist/
__pycache__/
storage/
.env
.env.*
```

Note `.gitignore` does **not** untrack files that are already committed. If
your branch already contains `node_modules`, clean it separately:

```bash
git rm -r --cached frontend/node_modules
git commit -m "Stop tracking node_modules"
```

Then add the ignore rules. Recreating the branch from `be_clone` is usually
less work than cleaning it in place.

---

## 9. What is not built yet

Be honest about these in the demo:

- **No search, no question answering.** Zero endpoints exist. That is Week 4
  work. If a screen shows an answer to a question, there is nothing behind it.
- **No document approval or versioning** (VQ-202, unmerged branch).
- **No password reset** (VQ-301, unmerged branch).
- **No per-tenant storage quota** and no OCR (VQ-201, unmerged branch).

Sprint 1 and 2 are tenant onboarding, document storage, and access control.
Frame the demo that way. It is a real deliverable and it does not need the Q&A
feature to stand up.

---

## 10. Order of work

1. Fix branch base (§1) and npm (§2)
2. Get `/health` returning 200 (§3)
3. Scaffold, port 5173, `.gitignore` first
4. Login page against the **real** `POST /auth/login` — no mocks. A build that
   compiles is not proof; you need a real token in a browser.
5. Then the rest of the screens
