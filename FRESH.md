# FE_clone — Frontend Work Log

Running log of frontend work on the `FE_clone` branch.

**Branch base:** `d90833d` ("Enable CORS for the frontend dev server")
**Backend branch built against:** `BE_clone` (identical commit, `d90833d`)

Every API fact below was read from source on this branch. File references are
given so each claim can be re-checked.

---

# PHASE 1 — ANALYSIS (no files modified)

Branch topology, verified with `git ls-files` / `git grep`:

| Branch | Commit | Role |
|---|---|---|
| `main` | `36ffb78` | colleague's branch — **DO NOT MODIFY** |
| `BE_clone` | `d90833d` | clean backend baseline — **READ-ONLY** |
| `FE_clone` | `d90833d` + doc commits | all frontend work happens here |

The previous frontend implementation was abandoned for endpoint mismatches.
This is a greenfield frontend on the clean backend baseline.

## 1. Project structure

Single Python backend at repo root. No frontend exists yet.

```
app/            4 routers, 8 models, 9 schemas, auth/, services/
tests/          12 test files
alembic/        migrations 001-006 (007-009 absent)
storage/        uploaded files, gitignored
```

## 2. Frontend framework / build setup — NONE

Verified three ways; all negative:

- `git ls-files frontend/` → **no tracked frontend files**
- anchored search for `*.js|jsx|ts|tsx|css|html|vue|svelte`, `package.json`,
  `vite.config`, `tailwind.config`, `tsconfig` → **zero matches**
- `frontend/` exists on disk but is **empty**; `frontend/node_modules` is absent

There is **no** `package.json`, no bundler, no framework, no entry point, no
dependency manifest, no `tsconfig`, no CSS. Items 3, 4, 5 and 6 of the brief
therefore have the answer **"does not exist"** — a framework, build tool, entry
point, dependency set, router and component set all have to be chosen from
scratch. Nothing to reuse.

> Note: a naive search for "react" returns hits, but every one is the substring
> in `reactivate` (tenant reactivation). There is no React in this repo.

## 7. Backend application structure

```
app/main.py        FastAPI app, CORS middleware, 4 routers, GET /health
app/config.py      pydantic-settings; CORS + lockout + JWT TTL
app/database.py    async SQLAlchemy engine, get_db, set_tenant_context
app/auth/          jwt.py, password.py, dependencies.py, permissions.py
app/models/        tenant, user, session, document, invite, audit_log
app/routes/        auth.py, documents.py, admin.py, invite.py
app/schemas/       auth.py, tenant.py, document.py
app/services/      storage.py
```

Routers mount at their own prefixes: `/auth`, `/documents`, `/admin` (plus
`/invite/accept` mounted with no prefix). 17 routes total, verified by grepping
every `@router.` / `@app.` decorator.

## 8. Complete route inventory (all 17)

| # | Method | Path | Auth | Success |
|---|---|---|---|---|
| 1 | GET | `/health` | none | 200 `{"status":"ok"}` |
| 2 | POST | `/auth/login` | none | 200 `TokenResponse` |
| 3 | POST | `/auth/refresh` | Bearer | 200 `TokenResponse` |
| 4 | POST | `/auth/logout` | Bearer | 200 `MessageResponse` |
| 5 | POST | `/documents` | Bearer | 201 `DocumentResponse` |
| 6 | GET | `/documents` | Bearer | 200 `DocumentListResponse` |
| 7 | GET | `/documents/usage` | Bearer | 200 `StorageUsageResponse` |
| 8 | GET | `/documents/{id}/preview` | Bearer | 200 (two shapes) |
| 9 | GET | `/documents/{id}/download` | Bearer | 200 `FileResponse` |
| 10 | DELETE | `/documents/{id}` | Bearer | 204 empty |
| 11 | POST | `/admin/tenants` | Bearer | 201 `TenantResponse` |
| 12 | GET | `/admin/tenants` | Bearer | 200 `TenantListResponse[]` |
| 13 | PATCH | `/admin/tenants/{id}/suspend` | Bearer | 200 `TenantResponse` |
| 14 | PATCH | `/admin/tenants/{id}/reactivate` | Bearer | 200 `TenantResponse` |
| 15 | POST | `/admin/tenants/{id}/invite` | Bearer | 201 `InviteResponse` |
| 16 | GET | `/admin/tenants/{id}/audit` | Bearer | 200 `AuditLogResponse[]` |
| 17 | POST | `/invite/accept` | none | 200 `InviteAcceptResponse` |

Note `/documents/usage` is declared **before** `/{document_id}/preview`
(documents.py:137 vs :163), so FastAPI matches it first — a document id of
`usage` cannot shadow it.

## 16. Search APIs — NONE EXIST

Searched all of `app/` and `tests/` for
`search|conversat|/ask|/query|/chat|embed|chunk|vector|pgvector`.
The only matches are `re.search` in `app/auth/password.py:17-23`.

There is no search, Q&A, chat, embedding, chunking or vector table, and no
conversation/message/feedback model. The branch is upload → list → preview →
download → delete only. **Do not build a question-answering screen against an
imagined endpoint** — the product's core feature does not exist yet.

## 18. Base URL and configuration

No backend URL is hardcoded anywhere in `app/`, and the frontend does not exist
yet, so nothing dictates one. `.env.example` sets `APP_PORT=8000`, so the
conventional local base is `http://127.0.0.1:8000`. The dev server should live
on **5173** to match the CORS allowlist.

`.env.example` (backend-only, read-only reference):

```
DATABASE_URL=postgresql+asyncpg://vaultiq:vaultiq_secret@localhost:5433/vaultiq
DATABASE_URL_SYNC=postgresql://vaultiq:vaultiq_secret@localhost:5433/vaultiq
JWT_SECRET=change-me-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
MAX_FAILED_ATTEMPTS=5
LOCKOUT_DURATION_MINUTES=15
APP_ENV=development
APP_PORT=8000
STORAGE_ROOT=./storage
```

`README.md` contains no `8000` / `localhost` / `uvicorn` / `5173` reference, so
it does not constrain the base URL.

## 12. Authorization mechanism

`HTTPBearer` (both `app/auth/dependencies.py:12` and `app/routes/auth.py:20`),
so the header is mandatory and there is **no cookie fallback** and **no query
parameter** path. Missing/malformed header → 403 from FastAPI's HTTPBearer
scheme, *not* 401. Send `Authorization: Bearer <token>` on every protected call.

Every request is re-validated server-side: the `jti` claim is looked up in the
`sessions` table and rejected if revoked (dependencies.py:37-44). Tokens are not
self-contained authority. Tenant context is set per request from the token, so
a user-supplied tenant id is never trusted.

## 9. Authentication / session mechanism

- `POST /auth/login` creates a `sessions` row, returns a JWT.
- Claims: `sub` (user uuid), `role`, `tenant_id` (null for super_admin), `jti`
  (session uuid), `iat`, `exp`.
- `JWT_EXPIRATION_HOURS=24`.
- `sessions.token_hash` is always written as `""` (auth.py:122) — hashes are not
  stored, so token theft cannot be detected after the fact.
- Suspending a tenant **deletes all its session rows** (admin.py:149-151), so
  every live token for that tenant fails on its next request with 401.
- `POST /auth/refresh` revokes the old session and issues a new one, so the
  previous token dies immediately.
- `POST /auth/logout` revokes by `jti`. It does **not** require the session to
  be un-revoked, and returns 200 even if the session row is already gone.

## 10. Login schema

Request `LoginRequest` (schemas/auth.py:7-10) — all fields required:

```json
{ "organisation_code": "ACME", "email": "user@acme.com", "password": "..." }
```

- `organisation_code`: 1-50 chars. The literal `SUPER` takes the platform path
  and requires `tenant_id IS NULL` + role `super_admin` (auth.py:50-58). The
  value is **not** uppercased — `super` will not match.
- Any other code is matched against `tenants.short_code` exactly (auth.py:61).
- `email`: 1-255 chars, no format validation on login.
- `password`: min 1 char. Strength is **not** checked on login — only on invite
  acceptance.

Response `TokenResponse` (schemas/auth.py:13-17) — the UI needs no JWT decoding:

```json
{ "access_token": "...", "token_type": "bearer",
  "role": "client_admin", "tenant_id": "uuid-or-null" }
```

## 11. Refresh / verify / logout

There is **no** "verify session" or "whoami" endpoint. The only way the client
learns who it is, is from the login/refresh response it already holds. On app
reload the client must either keep the token and role in storage, or call
`POST /auth/refresh` with the stored token to re-validate and get fresh
`role`/`tenant_id`.

- `POST /auth/refresh` — **no body**. `RefreshRequest` is an empty model
  (schemas/auth.py:20-21). Requires a valid Bearer token. Returns a new
  `TokenResponse`.
- `POST /auth/logout` — no body. Returns `{"detail": "Logged out"}`. Works even
  for an already-revoked session; an undecodable token gives 401.

## 13. Error and status responses

FastAPI `{"detail": "..."}`. **Validation errors (422) return `detail` as an
array of objects**, not a string — the client must handle both shapes.

Complete verbatim list of `detail` strings the backend can emit:

| Status | `detail` | Where |
|---|---|---|
| 400 | `Invalid credentials` | auth.py:95, 105, 116 |
| 400 | `Invalid or expired invite` | invite.py:37, 59, 65 |
| 400 | `<password rules joined by "; ">` | invite.py:41 |
| 400 | `Tenant already has a Client Admin` | invite.py:73, admin.py:236 |
| 400 | `User with this email already exists` | invite.py:81 |
| 400 | `Tenant already suspended` | admin.py:137 |
| 400 | `Cannot suspend offboarding tenant` | admin.py:140 |
| 400 | `Cannot suspend purged tenant` | admin.py:143 |
| 400 | `Tenant is not suspended` | admin.py:186 |
| 400 | `Can only invite for active tenants` | admin.py:225 |
| 400 | `Active invite already exists for this email` | admin.py:249 |
| 400 | `Filename is required` | documents.py:68 |
| 401 | `Invalid token` | dependencies.py:28, 52, 69, 93; auth.py:198 |
| 401 | `Session revoked` | dependencies.py:43 |
| 401 | `Invalid credentials` | auth.py:95, 105, 116 |
| 403 | `Tenant suspended` | auth.py:85, dependencies.py:123 |
| 403 | `Insufficient permissions` | auth.py (router guard) |
| 404 | `Document not found` | documents.py:182, 237, 276 |
| 404 | `Document file not found` | documents.py:192, 247 |
| 404 | `Tenant not found` | admin.py:134, 183, 222, 296 |
| 409 | `Tenant short code already exists` | admin.py:87 |
| 413 | `File too large. Max size: 50MB` | documents.py:44 |
| 415 | `Unsupported file type. Allowed: <list>` | documents.py:51 |

**429 — does not exist.** No rate limiting, no `slowapi`, no throttle anywhere
in `app/`. Login is protected by a 200 ms delay and account lockout instead.

**500 — no global handler.** The only middleware is CORS (main.py:22). Any
unhandled exception returns FastAPI's default `Internal Server Error`. See the
latent bug below — it is reachable.

### Latent backend bug: refresh raises 500 with two live sessions

`auth.py:149-155` does `select(Session).where(user_id, is_revoked == False)`
followed by `result.scalar_one_or_none()`. That helper **raises
`MultipleResultsFound` if more than one row matches**, which is an unhandled
500.

Reachable path: log in on two browsers (or two tabs, or a second device) for
the same user → two non-revoked sessions exist → either one calling
`POST /auth/refresh` throws 500 instead of rotating. The two login sessions
themselves are fine; only refresh breaks.

No test covers this (searched for `multiple_results` / `concurrent` /
`two session` — zero matches; `tests/test_auth.py` has 20 tests).

Frontend consequence: **wrap refresh in try/catch and fall back to logout**, and
do not treat 500 as retryable. A refresh triggered by a second concurrent tab is
a realistic scenario, not an edge case. This is a backend defect — the frontend
can only mitigate it. Do not edit `auth.py`.

## 14. Tenant / organisation APIs

`/admin/*` is gated by `require_roles("super_admin")` at the **router** level
(admin.py:33), so every one of the six returns 403 for any other role.

- `POST /admin/tenants` — `TenantCreate`: `short_code` (2-20, uppercased,
  `[A-Z0-9]`), `name`, `storage_quota_mb` optional `>= 0`. Bad format → 422,
  duplicate → 409.
- `GET /admin/tenants` — `TenantListResponse[]`, **not** paginated.
- `PATCH /admin/tenants/{id}/suspend` — no body. Deletes all tenant sessions.
- `PATCH /admin/tenants/{id}/reactivate` — no body. 400 if not suspended.
- `POST /admin/tenants/{id}/invite` — `InviteCreate`: `email` (validated),
  `expires_in_hours` default 168, range 1-8760. Returns the **plaintext code**;
  no mail relay exists so the operator must display and hand it over.
- `GET /admin/tenants/{id}/audit` — `AuditLogResponse[]`, newest first, **capped
  at 500** (admin.py:301-306), no pagination.

`TenantResponse` and `TenantListResponse` are **field-identical**
(schemas/tenant.py:38-59) — one TS type covers both.

`TenantSuspendRequest` / `TenantReactivateRequest` are empty placeholder models
and are never used by the routes; send no body.

`POST /invite/accept` is public: `code` (1-64) + `password` (8-128). This is the
**only** place password strength is enforced, and it is the only way a
`client_admin` user gets created. Codes are 43-char base64url matching
`^[A-Za-z0-9_-]{20,64}$` (invite.py:26), though the schema only requires 1 char.

## 15. Document / upload APIs

All require a tenant-scoped user; `super_admin` is denied on **every** one.

- `POST /documents` — `multipart/form-data`, single field `file`
  (documents.py:57). 201 `DocumentResponse`. **Roles: client_admin + employee.**
- `GET /documents` — `page` (default 1, min 1), `page_size` (default 20, min 1,
  **max 100**); ordered `created_at` desc. 200 `DocumentListResponse`.
- `GET /documents/usage` — **client_admin only**. 200 `StorageUsageResponse`.
- `GET /documents/{id}/preview` — 200, **two different shapes** (below).
- `GET /documents/{id}/download` — 200 `FileResponse`, original filename in
  `Content-Disposition`.
- `DELETE /documents/{id}` — **client_admin only**. 204, empty body.

Upload validation order (documents.py:40-53): size > 50 MB → 413; content type
not in the allowlist → 415; missing filename → 400. The allowlist is 7 types
(pdf, txt, markdown, docx, xls, xlsx, csv). Type comes from the **client-supplied
part header** and is stored on the record — a client-side extension check is a
convenience only, not a security control.

**Preview returns two shapes** (documents.py:196-215). Branch on
`preview === null`, not on mime type:

```jsonc
// text/*  -> 3 of the 7 allowlisted types
{ "document_id":"…", "filename":"…", "mime_type":"text/plain",
  "preview":"first 5000 chars", "truncated":false }

// everything else (pdf, docx, xls, xlsx)
{ "document_id":"…", "filename":"…", "mime_type":"application/pdf",
  "size_bytes":0, "preview":null,
  "message":"Preview not available for this file type" }
```

`truncated` exists **only** in the text branch; `size_bytes` and `message` exist
**only** in the other. Neither branch has a `response_model`, so these are
untyped dicts and TypeScript will need a discriminated union.

`GET /documents/usage` returns `tenant_id` (all-zeros
`00000000-0000-0000-0000-000000000000` for a super_admin context), plus
`total_documents`, `total_size_bytes`, `total_size_mb` (rounded to 2 dp).

## 17. Role-based behavior

Three roles (`schemas/tenant.py:16-19`): `super_admin`, `client_admin`,
`employee`. The matrix is code, not config — `ROLE_MATRIX` in
`app/auth/permissions.py`, applied by `require_roles()` /
`require_roles_with_tenant()`. `tests/test_permissions.py` walks every router
and fails on any un-annotated endpoint.

| Capability | super_admin | client_admin | employee |
|---|---|---|---|
| Create / suspend / reactivate tenant | yes | no | no |
| Issue invite | yes | no | no |
| Read audit log | yes | no | no |
| Upload document | **no** | yes | yes |
| List / preview / download | **no** | yes | yes |
| Delete document | **no** | yes | no |
| Storage usage | **no** | yes | no |

`super_admin` has `tenant_id: null`, is mapped to the all-zeros tenant id
(dependencies.py:14, 101-102), and **cannot reach document data at all**. Build
two separate surfaces — an operator console and a tenant app — and gate routes
client-side on the role from the login response, while still letting the backend
be the authority.

Also note: a `client_admin` sees only the first admin created via invite. There
is no user list, user create, or employee invite endpoint, so "manage staff"
cannot be built on this branch.

---

# Working rules

1. Work only on the frontend.
2. Never modify, rewrite, refactor or delete backend code.
3. Never modify `main`.
4. Never switch to `main` or `BE_clone` while working.
5. Treat existing backend code as read-only.
6. Never guess endpoints, request/response shapes, auth behaviour or status codes.
7. Do not start implementing UI until the relevant backend APIs have been read.
8. Do not overwrite existing project configuration unless the frontend requires it.
9. Keep the implementation clean, modular, maintainable, production-oriented.
10. No large unrelated changes.
11. Small focused changes; the project stays runnable after each major step.

---

## Backend source map

| Concern | File |
|---|---|
| App + CORS + router mounting | `app/main.py` |
| Settings (incl. CORS, lockout, JWT TTL) | `app/config.py` |
| Auth routes | `app/routes/auth.py` |
| Documents routes | `app/routes/documents.py` |
| Admin routes | `app/routes/admin.py` |
| Invite route | `app/routes/invite.py` |
| Role matrix (source of truth) | `app/auth/permissions.py` |
| Auth dependencies, tenant resolution | `app/auth/dependencies.py` |
| Password rules | `app/auth/password.py` |
| JWT encode/decode | `app/auth/jwt.py` |
| Schemas | `app/schemas/{auth,tenant,document}.py` |

---

## API contract

Base URL: `http://127.0.0.1:8000` unless the dev server is configured otherwise.

### CORS — `app/main.py:22-28`

```
allow_origins  = CORS_ALLOWED_ORIGINS  (default http://localhost:5173,http://127.0.0.1:5173)
allow_methods  = GET, POST, PATCH, DELETE, OPTIONS
allow_headers  = Authorization, Content-Type
allow_credentials = True
```

Exact-match origins, no wildcard. A different dev-server port requires setting
`CORS_ALLOWED_ORIGINS` in the backend `.env` — this is a backend config change
and must be requested, not made from the frontend.

> `POST /documents` sends `multipart/form-data`. `Content-Type` is in
> `allow_headers`, but when using `FormData` the browser must set the multipart
> boundary itself. Do **not** set `Content-Type` manually on that request.

### Authentication model

Login returns a JWT. Every protected call sends `Authorization: Bearer <token>`.

Token claims (`app/auth/jwt.py:16-24`):

| Claim | Meaning |
|---|---|
| `sub` | user UUID |
| `role` | `super_admin` \| `client_admin` \| `employee` |
| `tenant_id` | tenant UUID, or `null` for super_admin |
| `jti` | session id — the session is looked up server-side on every request |
| `iat`, `exp` | issued / expiry, `JWT_EXPIRATION_HOURS` (default 24) |

The response body (`app/schemas/auth.py:13-17`) carries everything the UI needs,
so **decode nothing client-side** — the role and tenant come from the response:

```json
{ "access_token": "...", "token_type": "bearer", "role": "client_admin", "tenant_id": "uuid-or-null" }
```

### Endpoints

#### Auth

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/auth/login` | none | Body `LoginRequest` |
| POST | `/auth/refresh` | Bearer | Rotates session; old token stops working |
| POST | `/auth/logout` | Bearer | Revokes session; returns `{"detail": "Logged out"}` |

`LoginRequest` — all three fields required (`app/schemas/auth.py:7-10`):

```json
{ "organisation_code": "ACME", "email": "...", "password": "..." }
```

- `organisation_code` 1–50 chars. `SUPER` selects the platform login path
  (`app/routes/auth.py:50`) — the user must have `tenant_id IS NULL` and role
  `super_admin`.
- `email` 1–255 chars.
- `password` min 1 char at the schema level. **Password strength is not
  validated on login** — it is only enforced when accepting an invite.

`POST /auth/refresh` takes no body. `RefreshRequest` is an empty model
(`app/schemas/auth.py:20-21`).

#### Documents — `app/routes/documents.py`

All require a tenant-scoped user. `super_admin` is **denied on every one**.

| Method | Path | Roles | Response |
|---|---|---|---|
| POST | `/documents` | client_admin, employee | 201 `DocumentResponse` |
| GET | `/documents` | client_admin, employee | 200 `DocumentListResponse` |
| GET | `/documents/usage` | client_admin | 200 `StorageUsageResponse` |
| GET | `/documents/{document_id}/preview` | client_admin, employee | 200, shape varies |
| GET | `/documents/{document_id}/download` | client_admin, employee | 200 file stream |
| DELETE | `/documents/{document_id}` | client_admin | 204, empty body |

> **Correction to the earlier note in this file:** upload is **not**
> client_admin-only. The role matrix allows `client_admin` **and** `employee`
> (`app/auth/permissions.py:30`, `app/routes/documents.py:58`). Only
> `GET /documents/usage` and `DELETE /documents/{id}` are client_admin-only.

**Upload** — `multipart/form-data`, single field named `file`
(`app/routes/documents.py:57`).

Validation order (`app/routes/documents.py:40-53`):
1. size > 50 MB → **413** `"File too large. Max size: 50MB"`
2. `content_type` not in the allowlist → **415** with the allowed list in `detail`
3. missing filename → **400** `"Filename is required"`

The allowlist is exactly 7 types (`app/routes/documents.py:26-35`):

```
application/pdf
text/plain
text/markdown
application/msword
application/vnd.openxmlformats-officedocument.wordprocessingml.document
application/vnd.ms-excel
application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
text/csv
```

Content type is taken from the **client-supplied part header**
(`file.content_type`) and is also written to the record
(`app/routes/documents.py:91`). Client-side extension checks are a convenience
only — the server trusts the declared type, not the bytes.

`DocumentResponse` (`app/schemas/document.py:17-24`):

```json
{
  "id": "uuid", "tenant_id": "uuid",
  "original_filename": "...", "stored_filename": "...",
  "mime_type": "...", "size_bytes": 0,
  "uploaded_by": "uuid", "created_at": "iso8601"
}
```

`GET /documents` — pagination (`app/routes/documents.py:102-134`):
`page` (default 1, min 1), `page_size` (default 20, min 1, **max 100**).
Ordered `created_at` descending.

```json
{ "documents": [DocumentResponse], "total": 0, "page": 1, "page_size": 20 }
```

`GET /documents/{id}/preview` — **the response shape is not uniform**
(`app/routes/documents.py:196-215`). For `text/*` it returns:

```json
{ "document_id": "...", "filename": "...", "mime_type": "...",
  "preview": "first 5000 chars", "truncated": false }
```

For any other type `preview` is `null` and two extra keys appear:

```json
{ "document_id": "...", "filename": "...", "mime_type": "...",
  "size_bytes": 0, "preview": null,
  "message": "Preview not available for this file type" }
```

The UI must branch on `preview === null`, not on mime type, to decide between
rendering text and showing the fallback. `truncated` is only present in the text
branch.

`GET /documents/{id}/download` streams the file with the **original** filename
as `Content-Disposition` (`app/routes/documents.py:250-254`). Trigger it via a
blob or an authenticated anchor — a plain `<a href>` will not carry the
`Authorization` header.

`DELETE /documents/{id}` returns **204 with no body**.

#### Admin — `app/routes/admin.py`

The whole router is gated by `require_roles("super_admin")` at the router level
(`app/routes/admin.py:33`). Any other role gets **403** for all of them.

| Method | Path | Body | Response |
|---|---|---|---|
| POST | `/admin/tenants` | `TenantCreate` | 201 `TenantResponse` |
| GET | `/admin/tenants` | — | 200 `TenantListResponse[]` |
| PATCH | `/admin/tenants/{tenant_id}/suspend` | none | 200 `TenantResponse` |
| PATCH | `/admin/tenants/{tenant_id}/reactivate` | none | 200 `TenantResponse` |
| POST | `/admin/tenants/{tenant_id}/invite` | `InviteCreate` | 201 `InviteResponse` |
| GET | `/admin/tenants/{tenant_id}/audit` | — | 200 `AuditLogResponse[]` |

`TenantCreate` (`app/schemas/tenant.py:22-35`):

```json
{ "short_code": "ACME", "name": "Acme Ltd", "storage_quota_mb": 2048 }
```

- `short_code` is uppercased and must match `[A-Z0-9]{2,20}` after
  normalisation. Violation → **422** (pydantic validation).
- `storage_quota_mb` optional, `>= 0`.
- Duplicate short code → **409** `"Tenant short code already exists"`.

Suspend deletes every session row for that tenant
(`app/routes/admin.py:149-151`), so **all that tenant's tokens die on the next
request** — a live client_admin tab will get 401 without any action from them.
Guard against this in the UI by handling 401 on any request as "log out".

Suspend state errors → **400**: already suspended, cannot suspend an `offboarding`
or `purged` tenant. Reactivate on a non-suspended tenant → **400**. Unknown
tenant → **404** `"Tenant not found"`.

`InviteCreate` (`app/schemas/tenant.py:70-72`): `email` (validated format),
`expires_in_hours` optional, default **168**, range 1–8760.

Invite creation fails with **400** if the tenant is not `active`, already has a
`client_admin`, or an unused unexpired invite exists for that email
(`app/routes/admin.py:224-249`).

`InviteResponse` returns the **code in plaintext** — there is no email relay, so
the operator must display and hand it over manually
(`app/routes/admin.py:37-39`; 43-char base64url).

`GET /admin/tenants/{id}/audit` returns **at most 500** entries, newest first
(`app/routes/admin.py:301-306`). There is no pagination parameter.

#### Public

| Method | Path | Auth | Response |
|---|---|---|---|
| GET | `/health` | none | `{"status": "ok"}` |
| POST | `/invite/accept` | none | 200 `InviteAcceptResponse` |

`InviteAcceptRequest` (`app/schemas/tenant.py:88-90`): `code` (1–64 chars),
`password` (8–128).

**Password strength is enforced here** (`app/auth/password.py:13-25`), returning
**400** with a `; `-joined message. All five rules:

1. at least 8 characters
2. one uppercase letter
3. one lowercase letter
4. one digit
5. one special character from ``!@#$%^&*()_+-=[]{};':"\|,.<>/?``

Failures also possible: `400` for invalid/expired/used invite, `400` if the
tenant already has a client_admin, `400` if that email already exists.

Success returns `{"detail", "tenant_id", "user_id"}` and the invite is marked
used — it cannot be reused.

---

## Roles

`super_admin` · `client_admin` · `employee` (`app/schemas/tenant.py:16-19`)

| Capability | super_admin | client_admin | employee |
|---|---|---|---|
| Create / suspend / reactivate tenant | yes | no | no |
| Issue invite | yes | no | no |
| Read audit log | yes | no | no |
| Upload document | **no** | yes | yes |
| List / preview / download document | **no** | yes | yes |
| Delete document | **no** | yes | no |
| Storage usage | **no** | yes | no |

A super_admin has `tenant_id: null` and cannot reach document data at all. Build
two separate surfaces: an operator console (tenants + audit) and a tenant app
(documents). Do not render a documents view for super_admin, and do not render
tenant management for anyone else.

---

## Error handling

Errors are FastAPI's `{"detail": "..."}` shape. Validation failures are **422**
with a `detail` **array** of objects, not a string — handle both:

```jsonc
// HTTPException
{ "detail": "Invalid credentials" }

// RequestValidationError — detail is an array
{ "detail": [ { "loc": ["body","short_code"], "msg": "...", "type": "..." } ] }
```

Status codes actually used by the backend:

| Code | Meaning here |
|---|---|
| 400 | Bad state — wrong password strength, already suspended, invite reuse |
| 401 | Bad/absent/expired/revoked token, or failed login |
| 403 | `Tenant suspended`, or `Insufficient permissions` (wrong role) |
| 404 | Resource not in your tenant — `Document not found`, `Tenant not found` |
| 409 | Duplicate tenant short code |
| 413 | File over 50 MB |
| 415 | Disallowed MIME type |
| 422 | Schema validation — including `short_code` format |

A cross-tenant document id returns **404**, never 403 — the backend does not
confirm that the resource exists elsewhere. The UI must not hint at other
tenants.

### Login security behaviour

Every failed login path returns the identical body `401 "Invalid credentials"`
and is padded to ~200 ms (`app/routes/auth.py:22`, enforced at lines 80-117). Do
not add client-side "email not found" style messaging — it would defeat this.

Account locks after **5** failed attempts for **15** minutes
(`app/config.py:13-14`). A locked account also returns `401 "Invalid credentials"`,
so the UI **cannot** distinguish lockout from wrong password. Show a neutral
message and let the user retry.

A suspended tenant with valid credentials returns **403 "Tenant suspended"** —
this one *is* distinguishable and should be shown as a clear state.

---

## Constraints the UI must respect

- **No generated text.** Answers are sentences extracted from the customer's own
  documents. No LLM, no paraphrase, no summarisation. (No search/Q&A endpoint
  exists on this branch yet — see Known gaps.)
- **Tenant isolation is absolute.** Cross-tenant access is refused without
  revealing that the resource or tenant exists. Never render a "you don't have
  access" state for another tenant's id.
- **No outbound network access.** No CDN, no external fonts, no analytics, no
  telemetry. Everything self-hosted.
- **No secrets in the client bundle.** `tenant_id` comes from the login response
  or the token — never from a value the user can edit. Never hardcode the JWT
  secret; it is backend-only.
- **Never store the token where other tenants' data could mix.** One auth
  context, cleared on logout and on any 401.

---

## Known gaps

- **No search, Q&A or chat endpoint exists on this branch.** The branch is
  upload → list → preview → download → delete only. Do not build an ask-a-question
  screen against an imagined endpoint.
- **No user-management endpoint.** There is no create/list/invite-employee API
  (`User` rows can only be created via the first-admin invite flow, or directly
  in the DB). "Client admins can manage their staff" is Sprint 3 work, not
  present here.
- **Migrations 007/008/009 are absent** (VQ-201 category/quota/OCR). They exist
  only on `origin/vq-201-tenant-upload` and were never merged to main. So
  `POST /documents` is the VQ-104 basic upload: no document category, no
  per-tenant quota enforcement, no OCR.
- **No password reset / forgot-password endpoint.** Out of scope until VQ-301.
- **Super Admin auth is broken under the production DB identity** (`vaultiq_app`).
  The RLS policies on `users`/`sessions` have no branch for `tenant_id IS NULL`,
  so super-admin login returns 401 under `vaultiq_app`. It works when the app
  connects as the `vaultiq` superuser. See `AGENTS.md` Known Defect #2. Plan for
  super-admin screens, but expect login failures until that is fixed.
- **CORS allowlist is exact-match** on `localhost:5173` / `127.0.0.1:5173`. Any
  other port needs a backend `.env` change.

---

## Log

<!-- Newest first. -->

### 2026-09-30 — PHASE 1 analysis complete (no files modified)

Read-only inspection. No project file was created, edited or deleted. Verified
the 18 analysis points with `git ls-files`, anchored `git grep`, the Grep tool,
and direct reads of every router, schema, model, auth module and config.

Established by inspection:

- Frontend framework, build setup, entry point, dependencies, routing and
  components **all do not exist** — confirmed three independent ways. There is
  nothing to reuse; the whole frontend is greenfield.
- **No search/Q&A API exists.** Repo-wide search for
  `search|conversat|ask|query|chat|embed|chunk|vector|pgvector` matched only
  `re.search` inside `password.py`.
- **No 429 anywhere** — no rate limiter, no throttle. Login is protected by a
  200 ms uniform delay plus 5-attempt/15-minute lockout instead.
- 17 routes total, all enumerated with method, path, auth and success shape.
- `HTTPBearer` only: no cookies, no query-param token. Missing header gives
  **403** from HTTPBearer, not 401.
- No "whoami"/session-verify endpoint. On reload, re-validate via
  `POST /auth/refresh`, which takes **no body**.
- No global exception handler; only CORS middleware.
- `.gitignore` has no `node_modules` entry — the cause of the 4340 dependency
  files committed last time. Should be added before scaffolding.

New finding worth acting on:

- **`POST /auth/refresh` returns 500 when a user has two live sessions.**
  `auth.py:155` uses `scalar_one_or_none()` over non-revoked sessions, which
  raises `MultipleResultsFound` on more than one row. Reachable by logging in
  twice (second browser/tab/device). Untested. Frontend must try/catch refresh
  and fall back to logout; never treat 500 as retryable. Backend defect — do not
  patch `auth.py` from this branch.

Also documented: the 200 ms delay applies to *all* login failures including
lockout, so the UI cannot distinguish lockout from a wrong password, while
`403 "Tenant suspended"` *is* distinguishable. And `organisation_code` is not
uppercased, so only the exact literal `SUPER` takes the platform login path.

### 2026-09-30 — branch prepared

- Repointed `FE_clone` from `36ffb78` to `d90833d` via `--force-with-lease`.
- Dropped 4367 frontend files, including 4340 tracked `node_modules` files.
- Gained the CORS commit (`app/config.py`, `app/main.py`, `tests/test_cors.py`).
- No backend work lost — `BE_clone` is a strict superset of the old `FE_clone`
  backend.
- `origin/main` untouched at `36ffb78`.
- `frontend/` directory is now empty on disk.

Anyone who pulled the old `FE_clone` needs
`git fetch && git reset --hard origin/FE_clone`.

### 2026-09-30 — backend API inspected, contract recorded

Read `app/main.py`, `config.py`, `auth/*`, `routes/{auth,documents,admin,invite}.py`,
`schemas/{auth,tenant,document}.py`, `models/user.py`. Replaced the earlier
hand-written endpoint summary with source-verified detail.

Corrections to the earlier version of this file:

- `POST /documents` allows **client_admin and employee**, not client_admin only.
- Preview returns **two different shapes**; the UI must branch on
  `preview === null`.
- Added the unlisted status codes: 400, 409, 413, 415, 422, and the 422
  array-shaped `detail`.
- Added lockout behaviour (5 attempts / 15 min) and the ~200 ms uniform login
  delay, and the rule that the UI must not reveal which field was wrong.
- Added suspend's side effect: it deletes all tenant sessions, so clients get
  401 on their next request with no action from them.
- Added the audit log's 500-entry cap.
- Added CORS: exact-match origins, and do not set `Content-Type` manually on
  multipart upload.
- Added Known gaps: no search/Q&A endpoint, no user management, no password
  reset, migrations 007–009 absent, super-admin auth broken under `vaultiq_app`.
