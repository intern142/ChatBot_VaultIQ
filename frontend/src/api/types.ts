export type UserRole = 'super_admin' | 'client_admin' | 'employee';

export type TenantStatus = 'active' | 'suspended' | 'offboarding' | 'purged';

// ===== Sprint 1/2 Compatible Types (for backward compatibility) =====

export interface Tenant {
  id: string;
  short_code: string;
  name: string;
  status: TenantStatus;
  storage_quota_mb: number | null;
  created_at: string;
  updated_at: string;
}

export interface AuthUser {
  name: string;
  role: UserRole;
  organization: string;
  email: string;
}

export interface LoginRequestLegacy {
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

export interface ApiErrorResponse {
  detail: string;
}

// ===== Backend Contract Types (Sprint 1/2/3) =====

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
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
  category: string;
  status: string;
  document_group_id: string;
  version_number: number;
  supersedes_id: string | null;
  approved_by: string | null;
  approved_at: string | null;
  decision_note: string | null;
  processing_status: ProcessingStatus;
  processing_error: string | null;
  processing_started_at: string | null;
  processing_completed_at: string | null;
  processing_version: number;
}

export type ProcessingStatus = 'queued' | 'processing' | 'ready' | 'failed';

export type JobStatus = 'queued' | 'processing' | 'done' | 'failed';

export interface JobResponse {
  id: string;
  status: JobStatus;
  retry_count: number;
  max_retries: number;
  last_error: string | null;
  payload: Record<string, unknown>;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
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

export interface ApprovalDecisionRequest {
  note?: string | null;
}

export interface SearchableDocumentsResponse {
  tenant_id: string;
  knowledge_base_version: number;
  documents: DocumentResponse[];
}

export interface VersionHistoryResponse {
  document_group_id: string;
  versions: DocumentResponse[];
}

export interface ProcessingStatusResponse {
  document_id: string;
  processing_status: ProcessingStatus;
  processing_error: string | null;
  processing_started_at: string | null;
  processing_completed_at: string | null;
  processing_version: number;
  job: JobResponse | null;
}

export interface ResetPasswordRequest {
  code: string;
  new_password: string;
}

export interface PasswordResetIssued {
  reset_code: string;
  expires_at: string;
}

export interface UserInviteCreate {
  email: string;
  role: string;
  expires_in_hours?: number;
}

export interface UserInviteIssued {
  code: string;
  email: string;
  role: string;
  expires_at: string;
}

export interface ImportRowResult {
  line: number;
  email: string;
  status: 'created' | 'not_created' | 'invalid';
  reason?: string | null;
}

export interface ImportResponse {
  applied: boolean;
  total_rows: number;
  created_count: number;
  invalid_count: number;
  rows: ImportRowResult[];
  message: string;
}

export interface DeactivateResponse {
  user: UserResponse;
  sessions_revoked: number;
  message: string;
}

export interface ReactivateResponse {
  user: UserResponse;
  message: string;
}

export interface RoleChangeRequest {
  role: string;
  current_password: string;
}

export interface RoleChangeResponse {
  user: UserResponse;
  sessions_revoked: boolean;
  message: string;
}

export interface UserResponse {
  id: string;
  tenant_id: string | null;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SearchRequest {
  query: string;
  top_k?: number;
  hybrid_weight?: number;
}

export interface SearchResult {
  document_id: string;
  chunk_index: number;
  content: string;
  score: number;
  original_filename: string;
}

export interface SearchResponse {
  results: SearchResult[];
  query: string;
  total_results: number;
}

export interface SuggestRequest {
  query: string;
  limit?: number;
}

export interface SuggestResponse {
  suggestions: string[];
}

export interface AnswerRequest {
  question: string;
  top_k?: number;
  hybrid_weight?: number;
}

export interface SpellCorrection {
  original_term: string;
  corrected_term: string;
}

export interface SpellcheckInfo {
  applied: boolean;
  original: string;
  corrected: string;
  corrections: SpellCorrection[];
}

export interface AnswerSource {
  document_id: string;
  chunk_index: number;
  original_filename: string;
  score: number;
  excerpt: string;
}

export interface AnswerResponse {
  question: string;
  answer_phrase: string;
  routing: string;
  confidence: number;
  sources: AnswerSource[];
  followups: string[];
  spellcheck: SpellcheckInfo;
  source_document_id: string | null;
  source_chunk_index: number | null;
}

export interface FeedbackCreate {
  vote: 1 | -1;
  comment?: string | null;
}

export interface FeedbackUpdate {
  vote?: 1 | -1 | null;
  comment?: string | null;
}

export interface FeedbackResponse {
  id: string;
  answer_id: string;
  user_id: string;
  vote: 1 | -1;
  comment: string | null;
  created_at: string;
  updated_at: string;
}

export interface FeedbackListResponse {
  feedback: FeedbackResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface OverviewResponse {
  questions_per_day_30d: Array<Record<string, unknown>>;
  active_users: number;
  answered_count: number;
  partial_count: number;
  not_found_count: number;
  avg_confidence: number | null;
}

export interface PaginatedResponse {
  items: Array<Record<string, unknown>>;
  total: number;
  limit: number;
  offset: number;
}

export interface TenantSettingsUpdateClientAdmin {
  display_name?: string | null;
  logo_path?: string | null;
  accent_colour?: string | null;
  not_found_message?: string | null;
  allowed_upload_formats?: string[] | null;
  conversation_retention_days?: number | null;
}

export interface TenantSettingsUpdateSuperAdmin extends TenantSettingsUpdateClientAdmin {
  storage_quota_mb?: number | null;
}

export interface TenantSettingsResponse {
  tenant_id: string;
  display_name: string | null;
  logo_path: string | null;
  accent_colour: string | null;
  not_found_message: string | null;
  allowed_upload_formats: string[] | null;
  conversation_retention_days: number | null;
  updated_by: string | null;
  updated_at: string;
}

export interface TenantPublicResponse {
  name: string;
  logo_path: string | null;
  accent_colour: string | null;
}

export interface LogoUploadResponse {
  path: string;
  size_bytes: number;
  mime_type: string;
}