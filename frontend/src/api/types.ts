export type UserRole = 'super_admin' | 'client_admin' | 'employee';
export type TenantStatus = 'active' | 'suspended' | 'offboarding' | 'purged';

export interface Tenant {
  id: string;
  short_code: string;
  name: string;
  status: TenantStatus;
  created_at: string;
  updated_at: string;
}

export interface User {
  id: string;
  tenant_id: string | null;
  email: string;
  role: UserRole;
  created_at: string;
  updated_at: string;
}

export interface AuthUser {
  name: string;
  role: UserRole;
  organization: string;
  email: string;
}

export interface LoginRequest {
  orgCode: string;
  username: string;
  email: string;
  password: string;
  role: UserRole;
}

export interface LoginResponse {
  accessToken: string;
  refreshToken: string;
  user: AuthUser;
}

export interface RefreshResponse {
  accessToken: string;
  refreshToken: string;
}

export interface VerifyResponse {
  ok: boolean;
}

export interface ApiErrorResponse {
  detail: string;
}

export interface TenantCreateRequest {
  short_code: string;
  name: string;
  storage_quota_gb: number;
  admin_email: string;
}

export interface TenantCreateResponse {
  tenant: Tenant;
  admin_invite_token: string;
  invite_url: string;
}

export interface TenantUpdateRequest {
  name?: string;
  status?: TenantStatus;
  storage_quota_gb?: number;
}

export interface QuotaResponse {
  used_gb: number;
  total_gb: number;
}