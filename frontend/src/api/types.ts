/*
 * VaultIQ API contract — shared request/response types and error model.
 * Single source of truth for both the mock backend and the real HTTP client.
 */

export interface LoginRequest {
  orgCode: string;
  username: string;
  email: string;
  password: string;
  userType: string;
}

export interface RegisterRequest {
  orgCode: string;
  email: string;
  password: string;
  role: string;
}

export interface UserInfo {
  name: string;
  role: string;
  organization: string;
  email: string;
}

export interface LoginResponse {
  accessToken: string;
  refreshToken: string;
  user: UserInfo;
}

export interface RefreshResponse {
  accessToken: string;
  refreshToken: string;
}

export interface VerifyResponse {
  ok: true;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    status: number;
  };
}

/**
 * Error thrown by every API driver (mock and real).
 * `message` always embeds the HTTP status so existing `err.message.includes('401')`
 * style checks in AuthContext keep working unchanged.
 */
export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(status: number, message: string, code?: string) {
    super(`${status} ${code ? code + ': ' : ''}${message}`);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

export interface SuperAdminStats {
  totalUsers: number;
  totalOrganizations: number;
  activeUsers: number;
  totalDocuments: number;
  pendingApproval: number;
  approvedDocuments: number;
}

export type DocumentStatus = 'pending' | 'approved' | 'rejected';

export interface Document {
  id: string;
  orgCode: string;
  name: string;
  originalName: string;
  size: number;
  mimeType: string;
  status: DocumentStatus;
  uploadedBy: string;
  uploadedAt: string;
  reviewedAt?: string;
  reviewedBy?: string;
}

export interface DocumentCounts {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
}

export interface UploadDocumentRequest {
  orgCode: string;
  file: File;
  uploadedBy: string;
}

export interface SearchDocumentsRequest {
  query: string;
  orgCode?: string;
}

export interface Tenant {
  id: string;
  short_code: string;
  name: string;
  status: 'active' | 'suspended' | 'offboarding' | 'purged';
  storage_quota_gb: number;
  created_at: string;
  updated_at: string;
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
  status?: Tenant['status'];
  storage_quota_gb?: number;
}

export type AuthApi = {
  login: (data: LoginRequest) => Promise<LoginResponse>;
  register: (data: RegisterRequest) => Promise<LoginResponse>;
  refresh: () => Promise<RefreshResponse>;
  logout: () => Promise<VerifyResponse>;
  verify: () => Promise<VerifyResponse>;
  getSuperAdminStats: () => Promise<SuperAdminStats>;
  getDocuments: (orgCode?: string) => Promise<Document[]>;
  getDocumentCounts: (orgCode?: string) => Promise<DocumentCounts>;
  uploadDocument: (data: UploadDocumentRequest) => Promise<Document>;
  updateDocumentStatus: (id: string, status: DocumentStatus, reviewedBy: string) => Promise<Document>;
  searchDocuments: (query: string, orgCode?: string) => Promise<Document[]>;
  getTenants: () => Promise<Tenant[]>;
  createTenant: (data: TenantCreateRequest) => Promise<TenantCreateResponse>;
  updateTenant: (id: string, data: TenantUpdateRequest) => Promise<Tenant>;
  suspendTenant: (id: string) => Promise<Tenant>;
  reactivateTenant: (id: string) => Promise<Tenant>;
};