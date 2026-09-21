# VaultIQ — Gate 1 · Acceptance Note — Sprint 1 (app shell)

Maps each acceptance criterion to the concrete evidence that proves it, and how to re-verify.

| # | Acceptance criterion | Evidence (in repo) | How to re-verify |
|---|---|---|---|
| 1 | Layout, routing, navigation exist for 3 roles: Super Admin, Client Admin, Employee | Role routes in `frontend/src/App.jsx` (ProtectedRoute per role); sidebar menus in `frontend/src/components/Layout/Sidebar.jsx`; screenshots-per-role (`frontend/screenshots-container/*.png`) | Login as each role → land on that role's dashboard; sidebar shows only its routes |
| 2 | A user never sees navigation for screens their role cannot use | `Sidebar.jsx` builds nav from the current role only; cross-role links absent; `AuthContext.jsx` gates routes | As Employee, confirm no `/admin/*` or `/super/*` items in the sidebar; manual URL to a foreign role redirects to that role's home |
| 3 | Current page survives browser refresh; sidebar stays fixed (HeXta fixes not regressed) | Session persisted in `localStorage` (`vaultiq_role`/`vaultiq_user`) and re-read in `AuthContext.jsx`; fixed-position CSS in Sidebar | Refresh mid-route → same screen returns; scroll a page → sidebar stays put |
| 4 | No fonts, icons, scripts, or styles from outside the app — works with cable pulled | `frontend/dist/bundle-external-scan` bundle scan = no external host refs; local inline SVG icons + system font stack | `Stop-Service`/unplug network → app still fully renders; inspect bundle for external `http` hosts (none) |
| 5 | Uses HeXta's monochrome design system | Monochrome tokens in `frontend/src/index.css` (grays/black, proof-grid), applied consistently | Visual check: grayscale UI, black primary, no color palette |

## Proof currently on file
- **Live container** serving the app: `docker ps` → `vaultiq-frontend` Up (healthy), `:8080->80`.
- **7 role screenshots** captured from that live container (desktop + phone): `frontend/screenshots-container/`
  — login, employee, client-admin, super-admin (each valid PNG, distinct per role).
- **External-host scan**: built bundle references no external hosts.

## Status
Gate-1 walkthrough ready for reviewer. Position note: this repo is VaultIQ's own; HeXta is
used strictly as design reference — codebase is built from scratch.
