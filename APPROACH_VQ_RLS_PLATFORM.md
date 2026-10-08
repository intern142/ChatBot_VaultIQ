# Approach Note: Fix Known Defect #2 — Super Admin Auth Under vaultiq_app

## Problem
Under `vaultiq_app` (NOBYPASSRLS), super_admin login returns 401 because:
1. Super admin user row has `tenant_id = NULL`
2. Super admin session row has `tenant_id = NULL`
3. RLS policies on `users` and `sessions` require `tenant_id = current_setting('app.current_tenant')::uuid`
4. Auth code sets context to dummy UUID `00000000-0000-0000-0000-000000000000` for super_admin
5. Policy mismatch: row has NULL, context has dummy UUID → row invisible → 401

## Solution
Modify RLS policies on `users` and `sessions` to allow the super_admin dummy UUID to match NULL tenant_id rows:

```sql
USING (
    tenant_id = current_setting('app.current_tenant', true)::uuid
    OR (
        tenant_id IS NULL
        AND current_setting('app.current_tenant', true) = '00000000-0000-0000-0000-000000000000'
    )
)
```

This allows:
- Normal tenant access: tenant_id matches context
- Super_admin access: row has tenant_id=NULL AND context is the super_admin dummy UUID

## Scope
- Migration: new version `008_rls_platform_accounts.py` (after 007)
- Tables: `users`, `sessions`
- No application code changes needed (auth already sets correct dummy UUID)

## Risks
- Low: only adds an OR branch for the specific super_admin dummy UUID
- No cross-tenant leakage: platform rows (NULL tenant_id) only visible when context is explicitly the super_admin UUID
- Tenant isolation preserved: normal tenants still only see their own data

## Testing
- Local: super_admin login under vaultiq_app works
- CI: vq-203 isolation suite passes (currently fails with 401 cascade)
- Existing tests: all 155+ tests still pass

## Gates
1. ✅ Approach note (this)
2. Implementation: migration + verify
3. Tests: local 155 passed, CI vq-203 green
4. Self-review
5. Code review
6. Live verify
7. Demo