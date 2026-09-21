/*
 * Real backend HTTP driver.
 * Implements the same AuthApi contract as the mock — reads tokens from
 * TokenStore so `AuthContext` never deals with wire details.
 */
import { API_BASE } from './config';
import { TokenStore } from '../lib/TokenStore';
import {
  ApiError,
  AuthApi,
  ApiErrorBody,
  LoginRequest,
  RegisterRequest,
  LoginResponse,
  RefreshResponse,
  VerifyResponse,
  SuperAdminStats,
} from './types';

type RequestOptions = {
  body?: unknown;
  withAccess?: boolean;
  withRefresh?: boolean;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };

  if (options.withAccess) {
    const access = TokenStore.getAccess();
    if (access) headers.Authorization = `Bearer ${access}`;
  }
  if (options.withRefresh) {
    const refresh = TokenStore.getRefresh();
    if (refresh) headers['X-Refresh-Token'] = refresh;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });

  if (!res.ok) {
    let body: ApiErrorBody | undefined;
    try {
      body = (await res.json()) as ApiErrorBody;
    } catch {
      // non-JSON error body — fall through to generic
    }
    throw new ApiError(
      res.status,
      body?.error?.message ?? res.statusText ?? 'Request failed',
      body?.error?.code
    );
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const realAuthApi: AuthApi = {
  login: (data: LoginRequest) => request<LoginResponse>('/auth/login', { body: data }),
  register: (data: RegisterRequest) => request<LoginResponse>('/auth/register', { body: data }),
  refresh: () => request<RefreshResponse>('/auth/refresh', { withRefresh: true }),
  logout: () => request<VerifyResponse>('/auth/logout', { withRefresh: true }),
  verify: () => request<VerifyResponse>('/auth/verify', { withAccess: true }),
  getSuperAdminStats: () => request<SuperAdminStats>('/admin/stats', { withAccess: true }),
};