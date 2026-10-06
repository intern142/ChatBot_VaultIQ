import { getApiBaseUrl } from './config';
import type {
  LoginRequest,
  LoginResponse,
  RefreshResponse,
  VerifyResponse,
  Tenant,
  TenantCreateRequest,
  TenantCreateResponse,
  TenantUpdateRequest,
  QuotaResponse,
} from './types';

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${getApiBaseUrl()}${endpoint}`;
  const token = localStorage.getItem('accessToken');

  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      errorData.detail || `HTTP error ${response.status}`,
      errorData.code,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

export const realApi = {
  async login(data: LoginRequest): Promise<LoginResponse> {
    return request<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async register(data: { orgCode: string; email: string; password: string; role: string }): Promise<LoginResponse> {
    return request<LoginResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async refresh(): Promise<RefreshResponse> {
    const refreshToken = localStorage.getItem('refreshToken');
    return request<RefreshResponse>('/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
  },

  async logout(): Promise<VerifyResponse> {
    const refreshToken = localStorage.getItem('refreshToken');
    const result = await request<VerifyResponse>('/auth/logout', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    return result;
  },

  async verify(): Promise<VerifyResponse> {
    return request<VerifyResponse>('/auth/verify');
  },

  async getTenants(): Promise<Tenant[]> {
    return request<Tenant[]>('/tenants');
  },

  async createTenant(data: TenantCreateRequest): Promise<TenantCreateResponse> {
    return request<TenantCreateResponse>('/tenants', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async updateTenant(id: string, data: TenantUpdateRequest): Promise<Tenant> {
    return request<Tenant>(`/tenants/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  },

  async suspendTenant(id: string): Promise<Tenant> {
    return request<Tenant>(`/tenants/${id}/suspend`, {
      method: 'POST',
    });
  },

  async reactivateTenant(id: string): Promise<Tenant> {
    return request<Tenant>(`/tenants/${id}/reactivate`, {
      method: 'POST',
    });
  },

  async getTenantQuota(): Promise<QuotaResponse> {
    return request<QuotaResponse>('/tenants/quota');
  },
};