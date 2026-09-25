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
  Document,
  DocumentCounts,
  UploadDocumentRequest,
  DocumentStatus,
  Tenant,
  TenantCreateRequest,
  TenantCreateResponse,
  TenantUpdateRequest,
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

async function uploadRequest<T>(path: string, formData: FormData, withAccess = true): Promise<T> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
  };

  if (withAccess) {
    const access = TokenStore.getAccess();
    if (access) headers.Authorization = `Bearer ${access}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers,
    credentials: 'include',
    body: formData,
  });

  if (!res.ok) {
    let body: ApiErrorBody | undefined;
    try {
      body = (await res.json()) as ApiErrorBody;
    } catch {
      // non-JSON error body
    }
    throw new ApiError(
      res.status,
      body?.error?.message ?? res.statusText ?? 'Upload failed',
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
  getDocuments: (orgCode?: string) => request<Document[]>(`/documents${orgCode ? `?orgCode=${orgCode}` : ''}`, { withAccess: true }),
  getDocumentCounts: (orgCode?: string) => request<DocumentCounts>(`/documents/counts${orgCode ? `?orgCode=${orgCode}` : ''}`, { withAccess: true }),
  uploadDocument: (data: UploadDocumentRequest) => {
    const formData = new FormData();
    formData.append('file', data.file);
    formData.append('orgCode', data.orgCode);
    formData.append('uploadedBy', data.uploadedBy);
    return uploadRequest<Document>('/documents/upload', formData);
  },
  updateDocumentStatus: (id: string, status: DocumentStatus, reviewedBy: string) => request<Document>(`/documents/${id}/status`, { body: { status, reviewedBy }, withAccess: true }),
  searchDocuments: (query: string, orgCode?: string) => request<Document[]>(`/documents/search?q=${encodeURIComponent(query)}${orgCode ? `&orgCode=${orgCode}` : ''}`, { withAccess: true }),
  getTenants: () => request<Tenant[]>('/admin/tenants', { withAccess: true }),
  createTenant: (data: TenantCreateRequest) => request<TenantCreateResponse>('/admin/tenants', { body: data, withAccess: true }),
  updateTenant: (id: string, data: TenantUpdateRequest) => request<Tenant>(`/admin/tenants/${id}`, { body: data, withAccess: true }),
  suspendTenant: (id: string) => request<Tenant>(`/admin/tenants/${id}/suspend`, { withAccess: true }),
  reactivateTenant: (id: string) => request<Tenant>(`/admin/tenants/${id}/reactivate`, { withAccess: true }),
};