import { request } from './client';

export interface TenantOverview {
  id: string;
  short_code: string;
  name: string;
  status: string;
  storage_used_mb: number;
  storage_quota_mb: number;
  document_count: number;
  user_count: number;
  active_user_count: number;
  created_at: string;
}

export interface TenantOverviewDetail extends TenantOverview {
  documents_last_30d: Array<{ date: string; count: number }>;
  questions_last_30d: Array<{ date: string; answered: number; partial: number; not_found: number }>;
  feedback_summary: { up: number; down: number };
}

export interface PlatformHealth {
  db: boolean;
  disk: boolean;
  processing_queue: boolean;
  no_internet: boolean;
  error_rate: number;
}

export interface PlatformStats {
  total_tenants: number;
  active_tenants: number;
  total_documents: number;
  total_users: number;
  total_questions_30d: number;
}

export const getPlatformOverview = () =>
  request<TenantOverview[]>('/admin/platform/overview');

export const getTenantOverviewDetail = (tenantId: string) =>
  request<TenantOverviewDetail>(`/admin/platform/overview/${tenantId}`);

export const getPlatformHealth = () =>
  request<PlatformHealth>('/admin/platform/health');

export const getPlatformStats = () =>
  request<PlatformStats>('/admin/platform/stats');