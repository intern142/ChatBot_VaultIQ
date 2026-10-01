import { request, setAuth, clearAuth } from './client';
import type { TokenResponse, MessageResponse } from './types';

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