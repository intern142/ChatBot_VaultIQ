# VaultIQ — Gate 1 · Approach Note — Sprint 1 (app shell)

**Goal of this sprint:** stand up the monochrome **application shell** that every later
screen slots into — 3 roles, role-scoped navigation, refresh survival, fully offline.

## What we build (and only this)
- **Layout + routing + nav** for 3 roles: Employee (`/employee/*`), Client Admin (`/admin/*`),
  Super Admin (`/super/*`), plus public Login/Register.
- **Role-gated navigation**: one sidebar source of truth (`AuthContext` role) → each role
  renders exactly its own menu entries; cross-role screens never link.
- **Refresh survival + fixed sidebar**: session lives in `localStorage` (`vaultiq_role`,
  `vaultiq_user`); protected routes re-read it on reload so the page comes back as-is;
  sidebar uses a fixed-position CSS layout (HeXta refresh/fixed fixes not regressed).
- **100% local assets**: inline SVG icon set, system font stack, monochrome tokens in our
  own `index.css` — nothing fetched from any external host (works with the cable pulled).
- **HeXta design language**: monochrome (grays/black) tokens, proof-grid backdrop — used as
  *design reference*; VaultIQ is built from scratch in its own repo. Nothing copied.

## How we sequence
1. Design system: monochrome tokens + local SVG icon set (the "skin").
2. Auth context + protected routes + role→default-screen map.
3. Sidebar/Layout shell; per-role route tables; role-scoped nav rendering.
4. Login/Register restyled in the same monochrome skin.
5. Build + evidence: bundle scan for external hosts; per-role screenshots (desktop+phone).

**Deployed as a live Docker container** (`node:20 build → nginx serve`) so login + each role
is proven against a running app at `localhost:8080`, not a local-only dev server.

## What we deliberately do NOT do this sprint
- No backend / API / database wiring (sprint-1 is the UI shell; auth is a localStorage demo).
- No real credentials or secrets; no external fonts/icons/scripts; no cross-role nav.
- No changes outside the VaultIQ repo (HeXta repo left untouched — reference only).
