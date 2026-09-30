# VaultIQ Frontend API Contract

**The backend is the source of truth. The frontend adapts to this document, never
the reverse.** If this file and the backend ever disagree, the backend is right
and this file is a bug.

## How this contract was produced

Machine-derived, not hand-written. FastAPI's own OpenAPI document was generated
from the imported app on the `FE_clone` baseline (`d90833d`):

```python
from app.main import app
spec = app.openapi()   # OpenAPI 3.1.0 — 15 paths, 17 operations, 19 schemas
```

Cross-checked by reading the source for anything the spec cannot express (role
gates, error strings, and the untyped preview/download responses). The generated
`openapi.json` lives in the temp dir, not the repo, so this branch gains no
build artefacts.

Everything below is a **read-only observation**. No backend file was modified.

## Base URL and transport

| Item | Value |
|---|---|
| Local base URL | `http://127.0.0.1:8000` (`APP_PORT=8000` in `.env.example`) |
| Dev server origin | `http://localhost:5173` or `http://127.0.0.1:5173` |
| Content type | `application/json`, except upload (`multipart/form-data`) |
| Auth scheme | `HTTPBearer` only — `securitySchemes: {HTTPBearer: {type: http, scheme: bearer}}` |

CORS (`app/main.py:22-28`) — exact-match origins, no wildcard:

```
allow_origins     = CORS_ALLOWED_ORIGINS  (default http://localhost:5173,http://127.0.0.1:5173)
allow_methods     = GET, POST, PATCH, DELETE, OPTIONS
allow_headers     = Authorization, Content-Type
allow_credentials = True
```

Any other dev port needs a backend `.env` change, which is out of scope for
frontend work.

## Authentication

`Authorization: Bearer <token>` on every protected operation. There is **no
cookie auth and no query-parameter auth** in the spec — a token in a URL would be
logged and is not supported.

The frontend needs **no JWT decoding**: `TokenResponse` carries `role` and
`tenant_id` directly. This avoids putting a JWT library in the bundle.

Operations with `security: NONE` in the spec — these are the only public ones:
`POST /auth/login`, `POST /invite/accept`, `GET /health`.

### Auth operation matrix

| Operation | Security in spec | Actual gate |
|---|---|---|
| `POST /auth/login` | none | public |
| `POST /auth/refresh` | HTTPBearer | valid session |
| `POST /auth/logout` | HTTPBearer | any decodable token |
| `POST /documents` | HTTPBearer | client_admin, employee |
| `GET /documents` | HTTPBearer | client_admin, employee |
| `GET /documents/usage` | HTTPBearer | client_admin |
| `GET /documents/{id}/preview` | HTTPBearer | client_admin, employee |
| `GET /documents/{id}/download` | HTTPBearer | client_admin, employee |
| `DELETE /documents/{id}` | HTTPBearer | client_admin |
| all `POST/GET/PATCH /admin/*` | HTTPBearer | super_admin (router-level) |
| `POST /invite/accept` | none | public |
| `GET /health` | none | public |

The spec records only *that* a route is secured, never *which role*, so the role
column is from `app/auth/permissions.py` and the routers. The backend remains the
authority — client-side gating is UX, not security.

## Response envelope conventions

- Success bodies are **bare objects**, never wrapped in `{data: ...}`.
- Errors are FastAPI's `{"detail": ...}`.
- **422 is a different shape:** `{"detail": [{loc, msg, type}, ...]}` — an
  **array**, while other errors give a **string**. One normaliser must handle
  both.
- `DELETE /documents/{id}` returns **204 with an empty body** — do not call
  `.json()` on it.
- `tenant_id` is `string | null`. `null` means super_admin.
- All timestamps are ISO-8601 strings.
- `TokenResponse.tenant_id` is required-but-nullable, so the key is always
  present; `InviteResponse.used_at` and the audit `actor_user_id` may be absent
  or null.

---

# Endpoints

## 1. `GET /health`

Public. `security: none`. Declared responses: `200`.

```json
{ "status": "ok" }
```

No `response_model` — untyped. Use for a dev reachability check only.

## 2. `POST /auth/login`

Public. `security: none`. Declared: `200`, `422`.

**Request** `LoginRequest` — all three required:

| Field | Type | Constraint |
|---|---|---|
| `organisation_code` | string | minLength 1, maxLength 50 |
| `email` | string | minLength 1, maxLength 255 |
| `password` | string | minLength 1 |

```json
{ "organisation_code": "ACME", "email": "admin@acme.com", "password": "..." }
```

```json
{ "organisation_code": "SUPER", "email": "platform@vaultiq.internal", "password": "..." }
```

Behaviour that is **not** in the schema and must be read from `auth.py`:

- `organisation_code` is **not** uppercased. Only the exact literal `SUPER`
  takes the platform path (`auth.py:50`); `super` will not match.
- `SUPER` requires `tenant_id IS NULL` **and** `role == super_admin`.
- Any other value is matched against `tenants.short_code` exactly.
- Password strength is **not** validated here — only on invite acceptance.

**Response 200** `TokenResponse`:

| Field | Type |
|---|---|
| `access_token` | string |
| `token_type` | string, default `"bearer"` |
| `role` | `super_admin` \| `client_admin` \| `employee` |
| `tenant_id` | string \| null (required key, may be null) |

**Errors**

| Status | `detail` | Note |
|---|---|---|
| 401 | `Invalid credentials` | wrong code, wrong email, wrong password, unknown user, **and lockout** — all identical |
| 403 | `Tenant suspended` | tenant is `suspended` or `offboarding`; the one distinguishable failure |
| 422 | array | malformed body |

All failure paths are padded to **200 ms** (`LOGIN_DELAY`, `auth.py:22`), so the
UI cannot time-distinguish either and must not attempt to. Lockout is **5 failed
attempts / 15 minutes** (`MAX_FAILED_ATTEMPTS`, `LOCKOUT_DURATION_MINUTES`) and
returns the same 401, so lockout is **not** distinguishable from a wrong
password. Do not show "email not found" or "account locked" messaging — that
defeats the uniform-response design.

## 3. `POST /auth/refresh`

`HTTPBearer`. Declared: `200`. **No request body** — the spec shows no
`requestBody`; `RefreshRequest` is an empty model (`schemas/auth.py:20-21`).

There is **no whoami/verify endpoint anywhere in the spec**. This is the only way
to re-validate a stored token and re-obtain `role`/`tenant_id` after a reload.

**Response 200** `TokenResponse` — same shape as login.

| Status | `detail` |
|---|---|
| 401 | `Invalid token` |
| 401 | `Session revoked` |
| 500 | see warning below |

> **Backend defect — the frontend must work around it.** `auth.py:155` calls
> `result.scalar_one_or_none()` over *all* non-revoked sessions for the user,
> which raises `MultipleResultsFound` on 2+ rows. A user logged in on two
> browsers/tabs/devices therefore gets a **500** from refresh, not a rotation. No
> test covers this. Wrap refresh in try/catch, fall back to logout, and never
> treat 500 as retryable. Do not patch `auth.py` from this branch.

## 4. `POST /auth/logout`

`HTTPBearer`. Declared: `200`. No body.

**Response 200** `MessageResponse`: `{ "detail": "Logged out" }`

| Status | `detail` |
|---|---|
| 401 | `Invalid token` (undecodable only) |

Succeeds even if the session is already revoked. Call it on explicit logout, but
do not depend on it for correctness — clear local state regardless.

## 5. `POST /documents`

`HTTPBearer`. Roles: **client_admin, employee**. Declared: `201`, `422`.

**Request:** `multipart/form-data`, single field **`file`** (required,
`Body_upload_document_documents_post`). `Content-Type: string` (binary).

Validation order (`documents.py:40-53`) — check in this order:

| # | Condition | Status | `detail` |
|---|---|---|---|
| 1 | size > 50 MB | 413 | `File too large. Max size: 50MB` |
| 2 | type not in allowlist | 415 | `Unsupported file type. Allowed: <sorted list>` |
| 3 | no filename | 400 | `Filename is required` |

Allowlist — exactly 7 values (`documents.py:26-35`):

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

The server reads the type from the **client-supplied part header** and stores it
on the record. A client-side extension check is a convenience, not a security
control — the server does not sniff bytes on this branch.

> **Do not set `Content-Type` manually on this request.** The browser must
> generate the multipart boundary. Set it only for the `json` requests.

**Response 201** `DocumentResponse` — all 8 fields required:

```json
{
  "id": "uuid", "tenant_id": "uuid",
  "original_filename": "policy.pdf", "stored_filename": "uuid.pdf",
  "mime_type": "application/pdf", "size_bytes": 12345,
  "uploaded_by": "uuid", "created_at": "2026-09-30T..."
}
```

## 6. `GET /documents`

`HTTPBearer`. Roles: client_admin, employee. Declared: `200`, `422`.

**Query** (both validated, violations → 422):

| Param | Type | Default | Min | Max |
|---|---|---|---|---|
| `page` | integer | 1 | 1 | — |
| `page_size` | integer | 20 | 1 | 100 |

**Response 200** `DocumentListResponse`:

| Field | Type |
|---|---|
| `documents` | `DocumentResponse[]` |
| `total` | integer (total matching, not page length) |
| `page` | integer |
| `page_size` | integer |

Ordered `created_at` descending. This is the only paginated endpoint.

## 7. `GET /documents/usage`

`HTTPBearer`. **client_admin only.** Declared: `200`. No params.

**Response 200** `StorageUsageResponse`:

| Field | Type | Note |
|---|---|---|
| `tenant_id` | string | all-zeros `00000000-0000-0000-0000-000000000000` for a super_admin context |
| `total_documents` | integer | |
| `total_size_bytes` | integer | |
| `total_size_mb` | number | rounded to 2 dp |

`total` is a **count of documents**, not bytes. Do not confuse the two names.

## 8. `GET /documents/{document_id}/preview`

`HTTPBearer`. Roles: client_admin, employee. Declared: `200`, `422`.

**No `response_model`** — the route returns a raw dict, so the spec gives **no
schema at all** for the success body. It is one of two different shapes
(`documents.py:196-215`), discriminated by `preview === null`:

```jsonc
// text/* (text/plain, text/markdown, text/csv only)
{
  "document_id": "uuid", "filename": "hr.txt", "mime_type": "text/plain",
  "preview": "first 5000 characters…",
  "truncated": false
}

// all other types (pdf, docx, xls, xlsx)
{
  "document_id": "uuid", "filename": "policy.pdf", "mime_type": "application/pdf",
  "size_bytes": 12345,
  "preview": null,
  "message": "Preview not available for this file type"
}
```

`truncated` exists **only** in the first shape; `size_bytes` and `message` exist
**only** in the second. Neither key is optional in its own shape. Branch on
`preview === null`, not on `mime_type`.

Text preview is capped at **5000 characters** and `truncated` is true when the
file is longer.

| Status | `detail` |
|---|---|
| 404 | `Document not found` — wrong tenant **or** deleted; indistinguishable by design |
| 404 | `Document file not found` — row exists, file gone from disk |

## 9. `GET /documents/{document_id}/download`

`HTTPBearer`. Roles: client_admin, employee. Declared: `200`, `422`.

Returns a `FileResponse` — a **binary stream**, not JSON. Original filename is
carried in `Content-Disposition`.

A plain `<a href>` will not work: the browser cannot attach the `Authorization`
header. Fetch as a blob, then create an object URL, and remember to
`URL.revokeObjectURL`.

| Status | `detail` |
|---|---|
| 404 | `Document not found` |
| 404 | `Document file not found` |

## 10. `DELETE /documents/{document_id}`

`HTTPBearer`. **client_admin only.** Declared: `204`, `422`.

No request body. **Response 204 with an empty body** — nothing to parse.

| Status | `detail` |
|---|---|
| 404 | `Document not found` |

Deletes the DB row and the file on disk. There is no undelete and no soft-delete
flag on this branch.

## 11. `GET /admin/tenants`

`HTTPBearer`. **super_admin only.** Declared: `200`. No params, not paginated.

**Response 200** `TenantListResponse[]` — a bare **array**, not an object.

`TenantListResponse` and `TenantResponse` are **field-identical** (both 7
required fields), so one TS type covers both:

| Field | Type |
|---|---|
| `id` | string (uuid) |
| `short_code` | string |
| `name` | string |
| `status` | `active` \| `suspended` \| `offboarding` \| `purged` |
| `storage_quota_mb` | integer \| null |
| `created_at` | string |
| `updated_at` | string |

## 12. `POST /admin/tenants`

`HTTPBearer`. **super_admin only.** Declared: `201`, `422`.

**Request** `TenantCreate`:

| Field | Type | Required | Constraint |
|---|---|---|---|
| `short_code` | string | yes | 1-50, then uppercased and must match `[A-Z0-9]{2,20}` |
| `name` | string | yes | 1-255 |
| `storage_quota_mb` | integer \| null | no | `>= 0` |

The `short_code` pattern is enforced by a pydantic validator, so a violation is a
**422** with a message, not a 400:

> `Short code must be 2-20 characters: uppercase letters and digits only`

The value is uppercased and trimmed server-side, so `"acme"` is accepted and
stored as `ACME`. Whitespace is stripped before validation.

**Response 201** `TenantResponse` (same 7 fields as above).

| Status | `detail` |
|---|---|
| 409 | `Tenant short code already exists` |
| 422 | array — includes the short_code pattern message |

## 13. `PATCH /admin/tenants/{tenant_id}/suspend`

`HTTPBearer`. **super_admin only.** Declared: `200`, `422`. **No body.**

`TenantSuspendRequest` is an empty placeholder model never used by the route, so
do not send one.

**Response 200** `TenantResponse` with `status: "suspended"`.

| Status | `detail` |
|---|---|
| 404 | `Tenant not found` |
| 400 | `Tenant already suspended` |
| 400 | `Cannot suspend offboarding tenant` |
| 400 | `Cannot suspend purged tenant` |

**Side effect that the frontend must handle:** suspending **deletes every session
row for that tenant** (`admin.py:149-151`). Every live token for that tenant then
fails on its next request with 401. A user in another tab is logged out with no
action from them. Any 401 anywhere in the app must therefore clear auth state
and route to login.

## 14. `PATCH /admin/tenants/{tenant_id}/reactivate`

`HTTPBearer`. **super_admin only.** Declared: `200`, `422`. **No body.**

**Response 200** `TenantResponse` with `status: "active"`.

| Status | `detail` |
|---|---|
| 404 | `Tenant not found` |
| 400 | `Tenant is not suspended` |

Reactivation does not restore sessions — the operator must re-invite or users
must log in again. Note the asymmetry with suspend: reactivate only accepts
`suspended`, not `offboarding`.

## 15. `POST /admin/tenants/{tenant_id}/invite`

`HTTPBearer`. **super_admin only.** Declared: `201`, `422`.

**Request** `InviteCreate`:

| Field | Type | Required | Default | Constraint |
|---|---|---|---|---|
| `email` | string (EmailStr) | yes | — | maxLength 255, format-validated |
| `expires_in_hours` | integer \| null | no | `168` (7 days) | 1 – 8760 |

**Response 201** `InviteResponse`:

| Field | Type | Note |
|---|---|---|
| `id` | string | |
| `tenant_id` | string | |
| `email` | string | |
| `code` | string | **plaintext, shown once** — 43-char base64url |
| `expires_at` | string | |
| `used_at` | string \| null | null until accepted |
| `created_by` | string | the super_admin's user id |
| `created_at` | string | |

There is **no mail relay** in this codebase. The operator must display the `code`
and hand it over manually, so the UI needs a copy-to-clipboard control and must
make clear it cannot be retrieved later.

| Status | `detail` |
|---|---|
| 404 | `Tenant not found` |
| 400 | `Can only invite for active tenants` |
| 400 | `Tenant already has a Client Admin` |
| 400 | `Active invite already exists for this email` |
| 422 | array |

## 16. `GET /admin/tenants/{tenant_id}/audit`

`HTTPBearer`. **super_admin only.** Declared: `200`, `422`. No params.

**Response 200** `AuditLogResponse[]` — a bare array, newest first, **capped at
500 entries** (`admin.py:301-306`). There is no pagination and no way to page
past 500, so the UI must say the list is capped rather than implying it is
complete.

| Field | Type | Note |
|---|---|---|
| `id` | string | |
| `tenant_id` | string | |
| `actor_user_id` | string \| null | null for system actions |
| `actor_role` | string | `super_admin`, or `system` for invite acceptance |
| `action` | string | e.g. `create_tenant`, `suspend_tenant`, `create_invite`, `accept_invite` |
| `target_type` | string | e.g. `tenant`, `user` |
| `target_id` | string | |
| `details` | object (JSON) | free-form, shape varies per action |
| `created_at` | string | |

`actor_role` is a plain string, **not** the `UserRole` enum — it can be `system`,
which is not in `UserRole`. Type it as `string`, not `UserRole`.

`details` is untyped JSON; treat every value as unknown.

| Status | `detail` |
|---|---|
| 404 | `Tenant not found` |

## 17. `POST /invite/accept`

Public. `security: none`. Declared: `200`, `422`.

The only way a `client_admin` user account is ever created. Bootstrap endpoint.

**Request** `InviteAcceptRequest`:

| Field | Type | Constraint |
|---|---|---|
| `code` | string | minLength 1, maxLength 64 |
| `password` | string | minLength 8, maxLength 128 |

**Password strength is enforced here** — the only place in the API. All five
rules, from `validate_password_strength` (`auth.py`/`password.py:13-25`), are
joined with `"; "` into a **400**:

1. at least 8 characters
2. one uppercase letter
3. one lowercase letter
4. one digit
5. one special character from ``!@#$%^&*()_+-=[]{};':"\|,.<>/?``

Example: `Password must be at least 8 characters; Password must contain at least one digit`

The client should validate these same five rules before submitting to avoid a
round trip, but the server is authoritative and its message should be shown
verbatim.

`code` is trimmed server-side. Actual codes match `^[A-Za-z0-9_-]{20,64}$`
(43 chars), though the schema only enforces 1-64 — so a too-short code passes
422 and fails at lookup with 400 instead.

**Response 200** `InviteAcceptResponse`:

| Field | Type |
|---|---|
| `detail` | string — `"Invite accepted successfully. You can now log in."` |
| `tenant_id` | string |
| `user_id` | string |

The invite is single-use; `used_at` is set and the same code returns 400.

| Status | `detail` |
|---|---|
| 400 | `Invalid or expired invite` — unknown, used, expired, **or tenant not active** |
| 400 | `<password rule errors joined by "; ">` |
| 400 | `Tenant already has a Client Admin` |
| 400 | `User with this email already exists` |
| 422 | array |

Note `Invalid or expired invite` deliberately covers four different causes.

---

# Cross-cutting error reference

Complete verbatim inventory of `detail` strings the backend can emit, gathered
from every `raise HTTPException` in `app/routes/`:

| Status | `detail` | Operation |
|---|---|---|
| 400 | `Invalid credentials` | login |
| 400 | `Invalid or expired invite` | invite accept |
| 400 | `<password rules>` | invite accept |
| 400 | `Tenant already has a Client Admin` | invite accept, create invite |
| 400 | `User with this email already exists` | invite accept |
| 400 | `Filename is required` | upload |
| 400 | `Tenant already suspended` | suspend |
| 400 | `Cannot suspend offboarding tenant` | suspend |
| 400 | `Cannot suspend purged tenant` | suspend |
| 400 | `Tenant is not suspended` | reactivate |
| 400 | `Can only invite for active tenants` | create invite |
| 400 | `Active invite already exists for this email` | create invite |
| 401 | `Invalid token` | any protected op, logout |
| 401 | `Session revoked` | any protected op |
| 401 | `Invalid credentials` | login |
| 403 | `Tenant suspended` | login, any protected op |
| 403 | `Insufficient permissions` | role gate |
| 403 | *(HTTPBearer default)* | missing/invalid `Authorization` header — **not** a `detail` string |
| 404 | `Document not found` | preview, download, delete |
| 404 | `Document file not found` | preview, download |
| 404 | `Tenant not found` | all tenant admin ops |
| 409 | `Tenant short code already exists` | create tenant |
| 413 | `File too large. Max size: 50MB` | upload |
| 415 | `Unsupported file type. Allowed: <list>` | upload |
| 422 | `[{loc, msg, type}, …]` | any schema violation |
| 500 | *(FastAPI default)* | unhandled — see the refresh defect |

**429 does not exist.** No rate limiter, no throttle, no `slowapi` anywhere in
`app/`. Login is protected by the 200 ms uniform delay and lockout instead. Do
not build a 429 handler expecting one to arrive.

**No global exception handler** — the only middleware is CORS. Every 500 is
FastAPI's default `Internal Server Error`.

## How the frontend must handle errors

1. Parse `detail` as **either** a string **or** an array; a type
   `unknown` → normalise in one place.
2. Treat 401 as "session ended": clear token, role and tenant, redirect to login.
   This is the normal outcome of an operator suspending a tenant.
3. Treat 403 as role or tenant-state, and distinguish by the `detail` string.
4. Treat 404 on a document as "gone" — never as "belongs to someone else",
   because the backend will not say that.
5. Do not retry 500. Do not retry 400/403/404/409/415.
6. Only 5xx and network errors are retryable, and even then not automatically.
7. Never surface raw `detail` for a 500 — it is not operator-safe text.

## Role matrix (source: `app/auth/permissions.py`)

| Capability | super_admin | client_admin | employee |
|---|---|---|---|
| Create tenant | yes | no | no |
| List tenants | yes | no | no |
| Suspend / reactivate tenant | yes | no | no |
| Create invite | yes | no | no |
| Read audit log | yes | no | no |
| Upload document | **no** | yes | yes |
| List documents | **no** | yes | yes |
| Preview / download document | **no** | yes | yes |
| Delete document | **no** | yes | no |
| Storage usage | **no** | yes | no |

`super_admin` has `tenant_id: null`, is mapped internally to the all-zeros
tenant id, and **cannot reach document data at all**. Build two disjoint
surfaces: an operator console and a tenant app.

## Not in the backend — do not build against these

Proven absent by searching the generated spec (15 paths) and all of `app/`:

- **No search, Q&A, chat, conversation, message, feedback or embedding
  endpoint.** No vector store, no chunking, no `pgvector`. The product's core
  question-answering feature does not exist on this branch.
- **No user management.** No list, create, update or deactivate user; no employee
  invite. A `client_admin` can only be the first admin created via
  `POST /invite/accept`. There is no way to add staff on this branch.
- **No password reset / forgot password** (VQ-301, not present).
- **No document versioning, categories, quotas or OCR.** Migrations 007-009 exist
  only on `origin/vq-201-tenant-upload` and never reached this baseline, so
  `POST /documents` is the basic VQ-104 upload.
- **No health detail.** `/health` returns only `{"status":"ok"}` — no version,
  no DB check.
- **No CORS for any other origin** without a backend `.env` change.

## Known backend defect affecting the frontend

`POST /auth/refresh` returns **500** when the user has two or more non-revoked
sessions, because `auth.py:155` uses `scalar_one_or_none()` across all of them.
Reachable by logging in twice. Untested in the backend suite.

Frontend mitigation: catch refresh failures, fall back to logout, and do not
retry. The fix belongs in the backend, not here.

## Provenance and maintenance

- Generated from `app.main:app` on `FE_clone` at `d90833d`.
- Regenerate after any backend change:
  `python -c "import json; from app.main import app; print(json.dumps(app.openapi(), indent=2))"`
- If a frontend call 404s, check this file against the regenerated spec before
  changing the frontend. The spec is authoritative.
- Role gates are **not** in the spec; they live in `app/auth/permissions.py` and
  are enforced by `tests/test_permissions.py`, which fails if an endpoint is
  left un-annotated.
