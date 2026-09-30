# FE_clone — Frontend Work Log

Running log of frontend work on the `FE_clone` branch.

**Branch base:** `d90833d` ("Enable CORS for the frontend dev server")
**Backend branch built against:** `BE_clone` (identical commit, `d90833d`)

Every API fact below was read from source on this branch. File references are
given so each claim can be re-checked.

---

## Working rules

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
