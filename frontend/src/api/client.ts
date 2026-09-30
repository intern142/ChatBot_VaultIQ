import { API_BASE_URL } from '../config';
import { normaliseError, ApiError } from './errors';

type RequestOptions = RequestInit & {
  params?: Record<string, string | number | boolean>;
  skipAuth?: boolean;
  skipRefreshOn401?: boolean;
};

const TOKEN_KEY = 'vaultiq_token';
const ROLE_KEY = 'vaultiq_role';
const TENANT_KEY = 'vaultiq_tenant_id';

export function buildUrl(path: string, params?: RequestOptions['params']): string {
  const url = new URL(`${API_BASE_URL}${path}`);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
}

function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

function getRole(): string | null {
  return localStorage.getItem(ROLE_KEY);
}

function getTenantId(): string | null {
  return localStorage.getItem(TENANT_KEY);
}

function setAuth(token: string, role: string, tenantId: string | null): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(ROLE_KEY, role);
  if (tenantId) localStorage.setItem(TENANT_KEY, tenantId);
  else localStorage.removeItem(TENANT_KEY);
}

function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
  localStorage.removeItem(TENANT_KEY);
}

let isRefreshing = false;

async function refreshToken(): Promise<boolean> {
  if (isRefreshing) return false;
  isRefreshing = true;
  try {
    const res = await fetch(buildUrl('/auth/refresh'), {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${getToken()}`,
      },
      credentials: 'omit',
    });
    if (!res.ok) return false;
    const data = await res.json();
    setAuth(data.access_token, data.role, data.tenant_id);
    return true;
  } catch {
    return false;
  } finally {
    isRefreshing = false;
  }
}

export async function request<T>(
  path: string,
  opts: RequestOptions = {}
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(opts.headers as Record<string, string>),
  };

  if (!opts.skipAuth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  if (opts.body instanceof FormData) {
    delete headers['Content-Type'];
  }

  const res = await fetch(buildUrl(path, opts.params), {
    ...opts,
    headers,
    credentials: 'omit',
  });

  if (res.status === 401 && !opts.skipRefreshOn401) {
    const refreshed = await refreshToken();
    if (refreshed) {
      return request(path, opts);
    }
    clearAuth();
    window.location.href = '/login';
    throw new ApiError('Session expired', 401);
  }

  const data = await res.json().catch(() => null);
  if (!res.ok) throw normaliseError(res.status, data);
  return data as T;
}

export { getToken, getRole, getTenantId, setAuth, clearAuth };