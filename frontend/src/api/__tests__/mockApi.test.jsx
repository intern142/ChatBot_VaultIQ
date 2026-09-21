/*
 * Mock backend — endpoint contract tests.
 * Verifies request/response formats and error responses match the spec,
 * independent of any UI. These run against the active driver via `authApi`
 * (mock by default; point at a real backend with VITE_API_MODE=real).
 */
import { describe, it, expect } from 'vitest';
import { API_MODE, authApi } from '../auth';
import { mockDb } from '../mock/db';

const seeded = {
  admin: { orgCode: 'ORG-12345', username: 'admin', email: 'admin@acme.com', password: 'Admin@123', userType: 'super-admin' },
  clientAdmin: { orgCode: 'ORG-12345', username: 'cadmin', email: 'cadmin@acme.com', password: 'Client@123', userType: 'admin' },
  employee: { orgCode: 'ORG-12345', username: 'employee', email: 'employee@acme.com', password: 'Employee@123', userType: 'employee' },
};

describe('auth login endpoint', () => {
  it('returns accessToken, refreshToken and user for valid credentials', async () => {
    const res = await authApi.login(seeded.admin);
    expect(res.accessToken).toBeTruthy();
    expect(res.refreshToken).toBeTruthy();
    expect(res.user).toMatchObject({ role: 'super-admin', email: 'admin@acme.com', organization: 'Acme Corp', name: 'System Admin' });
  });

  it('accepts admin userType for a client-admin account', async () => {
    const res = await authApi.login(seeded.clientAdmin);
    expect(res.user.role).toBe('client-admin');
  });

  it('maps "admin" userType to client-admin on mismatch → 401 INVALID_CREDENTIALS', async () => {
    const bad = { ...seeded.employee, userType: 'admin' };
    await expect(authApi.login(bad)).rejects.toSatisfy((e) => {
      return e.status === 401 && e.code === 'INVALID_CREDENTIALS';
    });
  });

  it('rejects a wrong password with 401 INVALID_CREDENTIALS', async () => {
    await expect(authApi.login({ ...seeded.admin, password: 'wrong' })).rejects.toSatisfy(
      (e) => e.status === 401 && e.code === 'INVALID_CREDENTIALS'
    );
  });

  it('rejects correct credentials with wrong org code → 403 PERMISSION_DENIED', async () => {
    await expect(authApi.login({ ...seeded.admin, orgCode: 'ORG-XXXXX' })).rejects.toSatisfy(
      (e) => e.status === 403 && e.code === 'PERMISSION_DENIED'
    );
  });
});

describe('auth register endpoint', () => {
  const newUser = { orgCode: 'ORG-12345', email: 'new.user@acme.com', password: 'Password@123', role: 'employee' };

  it('registers a new employee and returns tokens', async () => {
    const res = await authApi.register(newUser);
    expect(res.accessToken).toBeTruthy();
    expect(res.refreshToken).toBeTruthy();
    expect(res.user.role).toBe('employee');
    expect(res.user.email).toBe('new.user@acme.com');
  });

  it('rejects duplicate email with 409 EMAIL_EXISTS', async () => {
    await expect(authApi.register({ ...newUser, email: 'employee@acme.com' })).rejects.toSatisfy(
      (e) => e.status === 409 && e.code === 'EMAIL_EXISTS'
    );
  });

  it('rejects super-admin self signup with 403 SUPER_ADMIN_DISABLED', async () => {
    await expect(authApi.register({ ...newUser, email: 'sa.new@acme.com', role: 'super-admin' })).rejects.toSatisfy(
      (e) => e.status === 403 && e.code === 'SUPER_ADMIN_DISABLED'
    );
  });
});

describe('auth session lifecycle endpoints', () => {
  it('verify returns ok for a valid access token', async () => {
    const { accessToken, refreshToken } = await authApi.login(seeded.employee);
    sessionStorage.setItem('vaultiq_access', accessToken);
    localStorage.setItem('vaultiq_refresh', refreshToken);
    await expect(authApi.verify()).resolves.toEqual({ ok: true });
  });

  it('verify fails with 401 SESSION_EXPIRED for a bad token', async () => {
    sessionStorage.setItem('vaultiq_access', 'garbage.token.value');
    localStorage.setItem('vaultiq_refresh', 'irrelevant');
    await expect(authApi.verify()).rejects.toSatisfy(
      (e) => e.status === 401 && e.code === 'SESSION_EXPIRED'
    );
  });

  it('refresh rotates tokens and invalidates the old refresh token', async () => {
    const first = await authApi.login(seeded.employee);
    sessionStorage.setItem('vaultiq_access', first.accessToken);
    localStorage.setItem('vaultiq_refresh', first.refreshToken);

    const rotated = await authApi.refresh();
    expect(rotated.accessToken).toBeTruthy();
    expect(rotated.refreshToken).toBeTruthy();

    // Old refresh token is dead now.
    localStorage.setItem('vaultiq_refresh', first.refreshToken);
    await expect(authApi.refresh()).rejects.toSatisfy(
      (e) => e.status === 401 && e.code === 'SESSION_EXPIRED'
    );
    // New refresh token still works.
    localStorage.setItem('vaultiq_refresh', rotated.refreshToken);
    const rotatedAgain = await authApi.refresh();
    expect(rotatedAgain.accessToken).toBeTruthy();
  });

  it('logout revokes the session so refresh fails afterwards', async () => {
    const session = await authApi.login(seeded.employee);
    sessionStorage.setItem('vaultiq_access', session.accessToken);
    localStorage.setItem('vaultiq_refresh', session.refreshToken);

    await authApi.logout();
    await expect(authApi.refresh()).rejects.toSatisfy(
      (e) => e.status === 401 && e.code === 'SESSION_EXPIRED'
    );
  });
});

describe('mock database maintainability', () => {
  it('exposes seed orgs/users for tests', () => {
    expect(mockDb.findOrg('ORG-12345')).toBeDefined();
    expect(mockDb.findUser('admin@acme.com', 'admin')).toBeDefined();
  });

  it('reports the active mode so CI can assert the right backend', () => {
    expect(['mock', 'real']).toContain(API_MODE);
  });
});