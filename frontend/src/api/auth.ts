// FE2-1: auth API client (swap to real backend later)
export interface LoginRequest { orgCode: string; email: string; password: string }
export interface RegisterRequest extends LoginRequest { role: string }
export interface LoginResponse { 
  accessToken: string; 
  refreshToken: string; 
  user: { name: string; role: string; organization: string; email: string } 
}
export interface RefreshResponse { accessToken: string; refreshToken: string }

const BASE = import.meta.env.VITE_API_BASE ?? '/api';

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('LOGIN_FAILED');
  return res.json();
}

export const authApi = {
  login: (data: LoginRequest) => post<LoginResponse>('/auth/login', data),
  register: (data: RegisterRequest) => post<LoginResponse>('/auth/register', data),
  refresh: () => post<RefreshResponse>('/auth/refresh', {}),
  logout: () => post<void>('/auth/logout', {}),
  verify: () => post<{ ok: true }>('/auth/verify', {}),
};