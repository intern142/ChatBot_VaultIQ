# VQ-102 Gate 1: Approach Note — Database-Level Tenant Isolation

## Policy Design

**Tables to protect** (all client-data tables):
1. `users` — already has RLS policy, needs `FORCE ROW LEVEL SECURITY`
2. `sessions` — needs RLS enabled + policy + `FORCE RLS`
3. `documents` — already has RLS policy (from vq-104), needs `FORCE RLS`
4. Future tables: `chunks`, `embeddings`, `conversations`, `messages`, `feedback`, `audit_entries`, `ingestion_jobs`, `cached_answers` — all follow same pattern

**RLS Policy Pattern** (same for all tables):
```sql
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;
ALTER TABLE <table> FORCE ROW LEVEL SECURITY;  -- critical: prevents owner bypass
CREATE POLICY tenant_isolation ON <table>
USING (tenant_id = current_setting('app.current_tenant')::uuid);
```

## Tenant Context Setting

**Per-request** (already in VQ-103 middleware):
- Use `SET LOCAL app.current_tenant = '<tenant_id>'` (LOCAL = transaction-scoped, auto-resets)
- Executed at start of each request via middleware
- Cleared automatically at transaction end — no cross-request leakage

**Per-background-job**:
- Each job execution sets `SET LOCAL app.current_tenant = '<tenant_id>'` for its transaction
- Jobs process one tenant at a time (serialised per tenant)

## Database Roles

| Role | Purpose | RLS Bypass | Grants |
|------|---------|------------|--------|
| `vaultiq_app` | Application runtime | **NO BYPASSRLS** | SELECT/INSERT/UPDATE/DELETE on tenant tables |
| `vaultiq_super_admin` | Platform operator reads | NO BYPASSRLS | SELECT on `tenants` only (counts/status), NO access to `users`, `documents`, `sessions`, `chunks`, `messages` |
| `postgres` | Migrations only | BYPASSRLS (superuser) | DDL only, never used at runtime |

**Migration step**: Create roles and grants in new migration (003_rls_hardening.py)

## Connection Pool Configuration

- `pool_pre_ping=True` (already set)
- After each request: transaction ends → `SET LOCAL` auto-resets → connection returns to pool clean
- No manual `RESET` needed if using `SET LOCAL` correctly
- Verify: run cross-tenant test with pooled connections

## Migration Plan (one table per commit)

1. **Commit 1**: Add `FORCE ROW LEVEL SECURITY` to `users` table
2. **Commit 2**: Add RLS + FORCE RLS to `sessions` table (new migration)
3. **Commit 3**: Add `FORCE ROW LEVEL SECURITY` to `documents` table
4. **Commit 4**: Create `vaultiq_app` and `vaultiq_super_admin` roles + grants (new migration)
5. **Commit 5**: Update CI to run tests as `vaultiq_app` (not `postgres`)

## Tests to Write (Gate 3)

| Test | Purpose |
|------|---------|
| `test_rls_users_cross_tenant_read` | Tenant A cannot SELECT tenant B users |
| `test_rls_users_cross_tenant_write` | Tenant A cannot UPDATE/DELETE tenant B users |
| `test_rls_sessions_cross_tenant_read` | Tenant A cannot SELECT tenant B sessions |
| `test_rls_sessions_cross_tenant_write` | Tenant A cannot UPDATE/DELETE tenant B sessions |
| `test_rls_documents_cross_tenant_read` | Tenant A cannot SELECT tenant B documents |
| `test_rls_documents_cross_tenant_write` | Tenant A cannot UPDATE/DELETE tenant B documents |
| `test_no_tenant_context_returns_zero` | Session with no `app.current_tenant` returns 0 rows |
| `test_app_role_cannot_bypass_rls` | `vaultiq_app` role blocked by RLS (no BYPASSRLS) |
| `test_super_admin_role_limited_grants` | `vaultiq_super_admin` can only read `tenants` table |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| `SET` instead of `SET LOCAL` leaks tenant across transactions | Code review checklist: grep for `set_config.*app.current_tenant` — must be `SET LOCAL` |
| Missing `FORCE RLS` allows table owner bypass | Add `FORCE ROW LEVEL SECURITY` on every table; test with `vaultiq_app` role |
| Connection pool carries stale tenant | Use `SET LOCAL` (auto-reset); integration test with pooled connections |
| Super admin role accidentally gets data access | Explicit GRANT only on `tenants`; test denies on `users`/`documents` |

---

**Ready for reviewer approval before Gate 2 implementation.**