import { request } from './client';
import type {
  TenantSettingsResponse,
  TenantSettingsUpdateClientAdmin,
  LogoUploadResponse,
  TenantPublicResponse,
} from './types';

export const getMyTenantSettings = () =>
  request<TenantSettingsResponse>('/tenant/settings');

export const updateMyTenantSettings = (body: TenantSettingsUpdateClientAdmin) =>
  request<TenantSettingsResponse>('/tenant/settings', {
    method: 'PATCH',
    body: JSON.stringify(body),
  });

export const uploadMyTenantLogo = (file: File) => {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('filename', file.name);
  return request<LogoUploadResponse>('/tenant/settings/logo', {
    method: 'POST',
    body: fd,
  });
};

export const getTenantPublicSettings = (shortCode: string) =>
  request<TenantPublicResponse>(`/tenants/${encodeURIComponent(shortCode)}/public`);