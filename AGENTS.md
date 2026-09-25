# VaultIQ Backend

## Project State
- Current branch: main
- Current task: VQ-103 — Tenant context middleware (partial) + Staff/Admin APIs
- Status: **VQ-101 COMPLETE**, **VQ-103 PARTIAL** (DB + APIs done, middleware pending)

## Gate 3 Verification (2026-09-15) — VQ-101
- Migration up/down tested on seeded data
- `alembic upgrade head` → `alembic downgrade base` → `alembic upgrade head` ✅
- Model test: missing tenant_id fails for non-super_admin ✅
- Full test suite: **8/8 passed** ✅
- RLS cross-tenant read blocked ✅
- Post-downgrade re-apply: **8/8 passed** ✅

```
tests/test_tenant.py::test_create_tenant PASSED
tests/test_tenant.py::test_create_user_with_tenant PASSED
tests/test_tenant.py::test_create_user_without_tenant_fails PASSED
tests/test_tenant.py::test_create_user_with_fake_tenant_fails PASSED
tests/test_tenant.py::test_super_admin_without_tenant PASSED
tests/test_tenant.py::test_tenant_unique_short_code PASSED
tests/test_tenant.py::test_user_unique_email_per_tenant PASSED
tests/test_tenant.py::test_rls_blocks_cross_tenant_read PASSED
======================== 8 passed, 1 warning in 2.58s ========================
```

## Gate 4 Verification (2026-09-21) — VQ-103 (Partial)
- Migration 002 applied successfully (is_active, manager_id) ✅
- Staff/Admin API endpoints implemented ✅
- Schema updates complete (UserCreate, UserUpdate, UserResponse, UserWithSubordinates) ✅
- Tests for new endpoints: **pending**

## Tech Stack
- Backend: FastAPI (Python 3.11)
- Database: PostgreSQL 16
- ORM: SQLAlchemy 2.0 (async)
- Migrations: Alembic
- Auth: PyJWT (for later tasks)
- Testing: pytest + pytest-asyncio

## Sprint 1 Progress
- [x] VQ-101 — Tenant data model (COMPLETE)
- [ ] VQ-103 — Tenant context on every request (middleware pending)
- [x] VQ-103 — Staff/Admin API endpoints (COMPLETE)
- [ ] VQ-104 — Per-tenant document storage
- [ ] VQ-105 — Tenant-scoped login and session tokens

## What Was Completed

### VQ-101: Tenant Data Model & Migration
- **Tenant model**: UUID id, unique short_code, name, status enum (active/suspended/offboarding/purged), timestamps
- **User model**: UUID id, tenant_id FK (nullable for super_admin), email, password_hash, role enum (super_admin/client_admin/employee), timestamps
- **Constraints**: 
  - Unique constraint on (tenant_id, email) for per-tenant email uniqueness
  - Check constraint: super_admin must have NULL tenant_id; all other roles require tenant_id
- **Alembic migration 001_initial**: Creates tables, enums, indexes, and RLS policy
- **RLS policy on users table**: `tenant_id = current_setting('app.current_tenant')::uuid`
- All 8 tests passing covering model constraints and RLS

### VQ-103 (Partial): Staff/Admin APIs + DB Extensions
- **Migration 002_add_is_active_and_manager**: Added `is_active` (boolean, default true) and `manager_id` (self-referential FK, nullable) to users table
- **User model updated**: Added is_active, manager_id, and manager/subordinates relationship
- **API endpoints under `/tenants/{tenant_id}/`**:
  - `GET /staff` — List active employees (role=employee, is_active=true)
  - `GET /admins` — List admins (role=client_admin, is_active=true)
  - `GET /admins/{admin_id}/subordinates` — Get admin with direct reports (selectinload)
  - `GET /users/{user_id}` — Get specific user
  - `PATCH /users/{user_id}` — Update user (role, manager, is_active)
- **Schemas updated**: UserCreate, UserUpdate, UserResponse, UserWithSubordinates with new fields

## What Remains
- **VQ-103 (middleware)**: Tenant context middleware to set `app.current_tenant` on each request
- **VQ-103 (auth integration)**: Tenant-scoped database session dependency; extract tenant from JWT/header
- **VQ-104**: Per-tenant document storage schema and APIs
- **VQ-105**: Tenant-scoped login, JWT tokens with tenant claims, session management
- **Tests**: Add tests for new staff/admin API endpoints

## Files Changed

### Models & Migrations
- `app/models/tenant.py` — Tenant SQLAlchemy model
- `app/models/user.py` — User SQLAlchemy model (added is_active, manager_id, relationship)
- `app/models/__init__.py` — Model exports
- `alembic/versions/001_initial.py` — Initial migration with RLS
- `alembic/versions/002_add_is_active_and_manager.py` — Added is_active and manager_id columns

### Schemas & API
- `app/schemas/user.py` — User schemas (added is_active, manager_id, UserWithSubordinates)
- `app/schemas/tenant.py` — Tenant schemas (enums)
- `app/routers.py` — New: Tenant staff/admin API endpoints
- `app/main.py` — Updated to include tenants router

### Tests & Config
- `tests/test_tenant.py` — 8 test cases covering model constraints and RLS
- `tests/conftest.py` — Test fixtures (async engine, session, truncate tables)

## Bugs Discovered
- None

## Decisions Made
- Using PostgreSQL native enums for tenant_status and user_role
- RLS at database level for tenant isolation (not application-level only)
- super_admin role is the only one allowed without tenant_id
- Unique constraint on (tenant_id, email) allows same email across different tenants
- Cascade delete: deleting tenant removes all associated users
- Using UUID primary keys with gen_random_uuid()
- `is_active` defaults to true for new users
- `manager_id` is nullable, SET NULL on delete (subordinates become orphaned if manager deleted)
- Only client_admin role can be queried as "admin" in the admins endpoint
- Subordinates loaded via selectinload for efficient querying
- Check constraint enforces tenant_id rules at DB level (not just app level)

## Next Recommended Steps
1. **VQ-103 (remaining)**: Implement tenant context middleware to set `app.current_tenant` on each request
2. Add tenant context dependency for FastAPI routes (extract from JWT/header)
3. Create tenant-scoped database session dependency that auto-sets RLS context
4. **VQ-104**: Design document storage schema with tenant_id (consider pgvector for embeddings)
5. **VQ-105**: Implement JWT-based auth with tenant claims in token payload
6. Add tests for new staff/admin endpoints (list, get, update, subordinates)
7. Add integration tests for RLS with actual request context


# VaultIQ Frontend

## Sprint 1 Status — Gate 1 Complete (2026-09-15)
- **Application shell**: Layout, routing, role-scoped navigation for 3 roles (Employee, Client Admin, Super Admin)
- **Role-gated navigation**: Sidebar renders only links for current role; cross-role URLs redirect to role home
- **Refresh survival**: Session persisted in localStorage (`vaultiq_role`, `vaultiq_user`, tokens); re-read on reload
- **Fixed sidebar**: CSS `position: fixed` sidebar survives refresh; no layout shift
- **Zero external assets**: Inline SVG icons, system font stack, monochrome tokens in `index.css`; bundle scan confirms no external hosts
- **HeXta design language**: Monochrome proof-grid backdrop, grayscale tokens, black primary
- **Deployed**: Live Docker container (`vaultiq-frontend`) on `localhost:8080` with 7 role screenshots captured

## What Was Completed

### Application Shell & Routing
- **React 19 + React Router 7** with role-based route tree
- **AuthContext**: JWT access/refresh tokens in httpOnly-compatible TokenStore (localStorage); auto-refresh at 80% TTL; cross-tab logout broadcast
- **ProtectedRoute**: Role allow-list gating; unauthenticated → `/login?next=...`; wrong role → role home
- **Layout + Sidebar**: Fixed 232px sidebar (collapses to 68px icons on mobile); role-specific nav links; logout in footer
- **Login/Register**: Split-screen login with brand panel; register with role selection; lockout after 5 failures (15 min)

### Pages by Role
| Role | Path Prefix | Pages |
|------|-------------|-------|
| Employee | `/employee/*` | Dashboard (tabs: Dashboard, Upload, Ask, Profile), Chat, History |
| Client Admin | `/admin/*` | Dashboard (stats + recent docs), Documents (table + filters + upload modal), Staff, Settings |
| Super Admin | `/super/*` | Dashboard, Documents Upload, **Tenants (CRUD)**, Health, Settings |

### API Layer
- **Facade pattern** (`src/api/auth.ts`): Swaps `mockAuthApi` ↔ `realAuthApi` via `VITE_API_MODE`
- **Mock backend**: In-memory orgs/users/documents/**tenants**; 180ms simulated latency; seed data for 2 orgs, 5 users, 8 docs, 4 tenants
- **Real backend**: `fetch` with Bearer tokens; typed contracts in `src/api/types.ts`

### Design System (index.css)
- CSS custom properties for colors, spacing, radius, transitions, proof-grid backdrop
- Animation utilities: fade, slide, scale, shake, pulse, spin
- Responsive breakpoint at 768px (sidebar collapses to icon-only)
- Keyboard-first focus styles; reduced-motion support

### Testing
- **Vitest + React Testing Library** configured
- 18 tests covering LockoutBanner, LockoutWarning, Login, Register, AuthContext states
- Test setup mocks `authApi` for isolation

### Super Admin Tenant Management (NEW)
- **Tenant list table**: Code, Name, Status badges, Storage Quota (GB), Created, Actions
- **Create tenant modal**: Short code (uppercase), Name, Storage Quota (GB, min 1), First Admin Email — validation feedback
- **One-time invite**: Token-in-URL (`/register?invite=xxx&email=...`) shown once on success with copy button
- **Suspend/Reactivate**: Confirmation dialog (warning/info variants); only for active↔suspended states
- **Terminal states**: Offboarding/Purged shown read-only (no actions)
- **Reusable ConfirmDialog**: Variants (danger/warning/info), keyboard support (Esc/Enter), focus trap
- **Mock backend**: 4 seed tenants (active ×2, suspended, offboarding); full CRUD handlers

## What Remains
- **Backend wiring**: Switch `VITE_API_MODE=real` and connect to FastAPI endpoints
- **Documents API integration**: Upload, list, search, approve/reject workflows
- **Staff management UI**: Connect Client Admin Staff page to `/tenants/{id}/staff` endpoints
- **Chat/Ask backend**: RAG pipeline integration for employee questions
- **WebSocket/real-time**: Live document status updates, typing indicators

## Files Changed

### Core Application
- `frontend/src/main.jsx` — Entry point
- `frontend/src/App.jsx` — Route tree with role-based protected routes
- `frontend/src/index.css` — Complete design system (1762+ lines, added confirm dialog styles)
- `frontend/src/context/AuthContext.jsx` — Auth state, tokens, refresh, lockout (252 lines)
- `frontend/src/components/ProtectedRoute.jsx` — Role gating

### Layout & Navigation
- `frontend/src/components/Layout/Layout.jsx` — App shell with sidebar + outlet
- `frontend/src/components/Layout/Sidebar.jsx` — Role-scoped nav links (3 role configs)
- `frontend/src/components/Icons.jsx` — Inline SVG icon set (22 icons, added Pause/Play/Copy/Check/AlertTriangle/Info/Loader/X)

### Components (NEW)
- `frontend/src/components/ConfirmDialog.jsx` — Reusable confirmation modal (variants, keyboard, focus trap)

### Pages
- `frontend/src/pages/Login.jsx` — Split-screen login with brand panel
- `frontend/src/pages/Register.jsx` — Registration with role radios
- `frontend/src/pages/employee/Dashboard.jsx` — 4 tabs: overview, upload, ask, profile
- `frontend/src/pages/employee/Chat.jsx` — Chat placeholder
- `frontend/src/pages/employee/History.jsx` — Question history placeholder
- `frontend/src/pages/client-admin/Dashboard.jsx` — Stats grid + recent docs
- `frontend/src/pages/client-admin/Documents.jsx` — Table, filters, upload modal, status actions
- `frontend/src/pages/client-admin/Staff.jsx` — Staff list placeholder
- `frontend/src/pages/client-admin/Settings.jsx` — Settings placeholder
- `frontend/src/pages/super-admin/Dashboard.jsx` — Platform stats placeholder
- `frontend/src/pages/super-admin/Documents.jsx` — Cross-org document view
- `frontend/src/pages/super-admin/Tenants.tsx` — **Full tenant CRUD (table, create, suspend/reactivate, invite)**
- `frontend/src/pages/super-admin/Health.jsx` — Health check placeholder
- `frontend/src/pages/super-admin/Settings.jsx` — Platform settings placeholder

### API Layer
- `frontend/src/api/auth.ts` — Facade (mock/real switch)
- `frontend/src/api/config.ts` — VITE_API_MODE, VITE_API_BASE
- `frontend/src/api/types.ts` — TypeScript contracts (added Tenant, TenantCreateRequest/Response/UpdateRequest, extended AuthApi)
- `frontend/src/api/real.ts` — HTTP driver with TokenStore integration (added tenant methods)
- `frontend/src/api/mock/index.ts` — Mock driver with latency simulation
- `frontend/src/api/mock/db.ts` — In-memory seed data (added tenants, CRUD methods)
- `frontend/src/api/mock/handlers.ts` — Mock endpoint implementations (added tenant handlers)
- `frontend/src/api/mock/tokens.ts` — JWT-like token generation for mock
- `frontend/src/lib/TokenStore.ts` — localStorage token management

### Tests & Evidence
- `frontend/src/__tests__/auth.test.jsx` — 18 unit tests
- `frontend/src/__tests__/setup.js` — Test environment setup
- `frontend/screenshots-container/` — 7 role screenshots from live Docker container
- `frontend/screenshots-fe2/` — Additional dev screenshots

### Config
- `frontend/package.json` — Dependencies, scripts (dev, build, lint, test, preview)
- `frontend/vite.config.js` — Vite + Vitest config
- `frontend/public/icons.svg` — Inline SVG sprite (fallback)
- `frontend/public/*.html` — Boot HTML for each role (docker nginx)

## Bugs Discovered
- None blocking

## Decisions Made
- **No external dependencies** for UI: inline SVGs, system fonts, custom CSS tokens
- **Mock-first development**: Full in-memory backend enables UI work without API
- **Role-scoped routing**: Single route tree with `ProtectedRoute` wrappers per role
- **localStorage session**: Access + refresh tokens; survives refresh; cross-tab sync via storage event
- **Auto-refresh at 80% TTL**: Proactive token renewal avoids 401 mid-session
- **Lockout after 5 failures**: 15-minute cooldown; persists across refresh
- **Proof-grid backdrop**: CSS gradient grid on app pages; clean on auth pages
- **Fixed sidebar**: `position: fixed` with `z-index: 100`; main content offset by `var(--sidebar-w)`
- **Mobile-first responsive**: Sidebar collapses to 68px icon bar at ≤768px
- **Invite flow**: Token-in-URL shown once in modal; super admin copies/hands over manually (no email infra)
- **Storage quota**: Integer GB (simpler UI); default 10 GB, min 1 GB
- **Tenant status terminal states**: Offboarding/Purged are read-only (no reactivate)

## Next Recommended Steps
1. **VQ-105 integration**: Set `VITE_API_MODE=real`, `VITE_API_BASE=http://localhost:8000`; wire real auth flow
2. **Documents API**: Connect Client Admin Documents page to `/tenants/{id}/documents` endpoints
3. **Staff API**: Connect Client Admin Staff page to `/tenants/{id}/staff` + `/admins` endpoints
4. **Chat RAG**: Build `/api/chat` endpoint; connect Employee Ask tab
5. **E2E tests**: Add Playwright tests for critical paths (login → dashboard → logout)
6. **Accessibility audit**: Verify WCAG AA (focus order, ARIA labels, contrast)