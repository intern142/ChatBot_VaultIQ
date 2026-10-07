import { request } from './client';
import type {
  TenantResponse,
  TenantCreate,
  InviteCreate,
  InviteResponse,
  AuditLogResponse,
  TenantSettingsResponse,
  TenantSettingsUpdateSuperAdmin,
} from './types';

export const listTenants = () =>
  request<TenantResponse[]>('/admin/tenants');

export const createTenant = (body: TenantCreate) =>
  request<TenantResponse>('/admin/tenants', {
    method: 'POST',
    body: JSON.stringify(body),
  });

export const suspendTenant = (id: string) =>
  request<TenantResponse>(`/admin/tenants/${id}/suspend`, {
    method: 'PATCH',
  });

export const reactivateTenant = (id: string) =>
  request<TenantResponse>(`/admin/tenants/${id}/reactivate`, {
    method: 'PATCH',
  });

export const inviteTenantAdmin = (id: string, body: InviteCreate) =>
  request<InviteResponse>(`/admin/tenants/${id}/invite`, {
    method: 'POST',
    body: JSON.stringify(body),
  });

export const getTenantAudit = (id: string) =>
  request<AuditLogResponse[]>(`/admin/tenants/${id}/audit`);

export const getTenantSettings = (id: string) =>
  request<TenantSettingsResponse>(`/admin/tenants/${id}/settings`);

export const updateTenantSettings = (id: string, body: TenantSettingsUpdateSuperAdmin) =>
  request<TenantSettingsResponse>(`/admin/tenants/${id}/settings`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });