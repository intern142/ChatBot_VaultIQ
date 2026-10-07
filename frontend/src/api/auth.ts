import { request, setAuth, clearAuth } from './client';
import type { TokenResponse, MessageResponse, ResetPasswordRequest, Tenant, TenantUpdateRequest, QuotaResponse } from './types';
import { listTenants, createTenant, suspendTenant, reactivateTenant, getTenantSettings, updateTenantSettings } from './admin';

export const login = (body: { organisation_code: string; email: string; password: string }) =>
  request<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(body),
    skipAuth: true,
    skipRefreshOn401: true,
  }).then((data) => {
    setAuth(data.access_token, data.role, data.tenant_id);
    return data;
  });

export const refresh = () =>
  request<TokenResponse>('/auth/refresh', {
    method: 'POST',
    skipRefreshOn401: true,
  }).then((data) => {
    setAuth(data.access_token, data.role, data.tenant_id);
    return data;
  });

export const logout = () =>
  request<MessageResponse>('/auth/logout', {
    method: 'POST',
    skipRefreshOn401: true,
  }).finally(clearAuth);

export const resetPassword = (body: ResetPasswordRequest) =>
  request<MessageResponse>('/auth/reset-password', {
    method: 'POST',
    body: JSON.stringify(body),
    skipAuth: true,
    skipRefreshOn401: true,
  });

// Default export for backward compatibility with Sprint 1/2 components
const authApi = {
  login,
  refresh,
  logout,
  getTenants: listTenants,
  createTenant,
  updateTenant: (id: string, data: TenantUpdateRequest) =>
    request<Tenant>(`/admin/tenants/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  suspendTenant,
  reactivateTenant,
  getTenantQuota: () => request<QuotaResponse>('/tenants/quota'),
  // Tenant settings (super_admin)
  getTenantSettings,
  updateTenantSettings,
};

export default authApi;