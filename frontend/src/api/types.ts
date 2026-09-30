export type UserRole = 'super_admin' | 'client_admin' | 'employee';

export type TenantStatus = 'active' | 'suspended' | 'offboarding' | 'purged';

export interface TokenResponse {
  access_token: string;
  token_type?: string;
  role: UserRole;
  tenant_id: string | null;
}

export interface LoginRequest {
  organisation_code: string;
  email: string;
  password: string;
}

export interface MessageResponse {
  detail: string;
}

export interface InviteAcceptRequest {
  code: string;
  password: string;
}

export interface InviteAcceptResponse {
  detail: string;
  tenant_id: string;
  user_id: string;
}

export interface TenantCreate {
  short_code: string;
  name: string;
  storage_quota_mb?: number | null;
}

export interface TenantResponse {
  id: string;
  short_code: string;
  name: string;
  status: TenantStatus;
  storage_quota_mb: number | null;
  created_at: string;
  updated_at: string;
}

export type TenantListResponse = TenantResponse;

export interface InviteCreate {
  email: string;
  expires_in_hours?: number | null;
}

export interface InviteResponse {
  id: string;
  tenant_id: string;
  email: string;
  code: string;
  expires_at: string;
  used_at: string | null;
  created_by: string;
  created_at: string;
}

export interface AuditLogResponse {
  id: string;
  tenant_id: string;
  actor_user_id: string | null;
  actor_role: string;
  action: string;
  target_type: string;
  target_id: string;
  details: Record<string, unknown>;
  created_at: string;
}

export interface DocumentResponse {
  id: string;
  tenant_id: string;
  original_filename: string;
  stored_filename: string;
  mime_type: string;
  size_bytes: number;
  uploaded_by: string;
  created_at: string;
}

export interface DocumentListResponse {
  documents: DocumentResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface StorageUsageResponse {
  tenant_id: string;
  total_documents: number;
  total_size_bytes: number;
  total_size_mb: number;
}

export type PreviewTextResponse = {
  document_id: string;
  filename: string;
  mime_type: `text/${string}`;
  preview: string;
  truncated: boolean;
};

export type PreviewOtherResponse = {
  document_id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  preview: null;
  message: string;
};

export type PreviewResponse = PreviewTextResponse | PreviewOtherResponse;