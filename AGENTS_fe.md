# VaultIQ Frontend

## 1. What Was Completed
- React + Vite frontend running on **port 5173**
- Configured API base URL: `http://localhost:8001` via `frontend/.env`
- Login page with organization code, username, email, password, role fields
- Auth context with token storage (localStorage), refresh, logout
- Dashboard with role-based quick actions (super_admin, client_admin, employee)
- Tenants page with CRUD, search, filter, suspend/reactivate
- CORS configured in backend for `localhost:5173`
- Mock API mode for development (switchable via `VITE_API_MODE`)

## 2. What Remains
- Auth routes not implemented on main branch (only `/health` exists)
- Login fails with 404 — `/auth/login` endpoint missing
- Need to switch to `vq-202-approval-versioning` branch for auth routes
- Frontend expects payload: `{organisation_code, email, password}` (no username/role)
- Super Admin login has known defect (#2) — use client_admin/employee for testing

## 3. Files Changed
- `frontend/.env` — Added `VITE_API_BASE_URL=http://localhost:8001`, `VITE_API_MODE=real`
- `app/main.py` — Added CORS middleware for `localhost:5173`, `localhost:8080`
- `frontend/src/api/config.ts` — Reads `VITE_API_BASE_URL` env var
- `frontend/src/api/real.ts` — Real API implementation (login, register, tenants, auth)

## 4. Bugs Discovered
- **404 on `/auth/login`**: Main branch lacks auth routes; available on `vq-202-approval-versioning`
- **Port conflict**: Backend on 8000 conflicts with another app; using 8001 instead
- **Super Admin defect**: Known Defect #2 causes 401 on hardened deployments
- **Frontend payload mismatch**: Form sends `username`, `role` but API expects only `organisation_code`, `email`, `password`
- **Mock DB credentials**: Test users use `Admin@123`/`Client@123`/`Employee@123`, not `AdminPass1!`

## 5. Decisions Made
- Use `pgvector/pgvector:pg16` Docker container on port 5433 (not local PostgreSQL)
- Backend on port 8001 to avoid conflict with existing app on 8000
- Frontend dev server on 5173; Docker frontend on 8080
- CORS allows `localhost:5173`, `localhost:8080`, `127.0.0.1:5173`
- Mock API mode enabled by default (`VITE_API_MODE=mock`); switched to `real` for integration

## 6. Next Recommended Steps
1. **Switch to auth branch**: `git checkout vq-202-approval-versioning` (stash local changes first)
2. **Align payload**: Update frontend Login form to send `{organisation_code, email, password}` only
3. **Seed test users**: Match mock DB credentials (`admin@acme.com`/`Admin@123` etc.)
4. **Implement real API routes** on main if staying on main: `POST /auth/login`, `GET /tenants`, etc.
5. **Verify CORS** works end-to-end after branch switch
6. **Test login flow** with `client_admin`/`employee` roles (Super Admin has Known Defect #2)