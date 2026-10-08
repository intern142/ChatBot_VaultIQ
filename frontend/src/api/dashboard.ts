import { request, getToken, buildUrl } from './client';
import { isMockMode } from './config';
import { normaliseError } from './errors';
import type { OverviewResponse, PaginatedResponse } from './types';

export type DashboardEntity = 'documents' | 'users' | 'audit' | 'feedback';

export interface DashboardListParams {
  limit?: number;
  offset?: number;
  search?: string;
}

const isDashboardEntity = (value: string): value is DashboardEntity =>
  value === 'documents' || value === 'users' || value === 'audit' || value === 'feedback';

export const getDashboardOverview = async (): Promise<OverviewResponse> => {
  if (isMockMode()) {
    const { handleDashboardOverview } = await import('./mock/handlers');
    return handleDashboardOverview();
  }
  return request<OverviewResponse>('/dashboard/overview');
};

export const getDashboardList = async (
  entity: DashboardEntity,
  params?: DashboardListParams,
): Promise<PaginatedResponse> => {
  if (isMockMode()) {
    const { handleDashboardList } = await import('./mock/handlers');
    return handleDashboardList(entity, params);
  }
  const queryParams: Record<string, string | number | boolean> = {};
  if (params?.limit !== undefined) queryParams.limit = params.limit;
  if (params?.offset !== undefined) queryParams.offset = params.offset;
  if (params?.search !== undefined) queryParams.search = params.search;
  return request<PaginatedResponse>(`/dashboard/${entity}`, { params: queryParams });
};

export const getKnowledgeGaps = async (
  params?: DashboardListParams,
): Promise<PaginatedResponse> => {
  if (isMockMode()) {
    const { handleDashboardList } = await import('./mock/handlers');
    return handleDashboardList('knowledge-gaps', params);
  }
  const queryParams: Record<string, string | number | boolean> = {};
  if (params?.limit !== undefined) queryParams.limit = params.limit;
  if (params?.offset !== undefined) queryParams.offset = params.offset;
  return request<PaginatedResponse>('/dashboard/knowledge-gaps', { params: queryParams });
};

export const downloadDashboardCsv = async (entity: string): Promise<Blob> => {
  if (isMockMode()) {
    if (!isDashboardEntity(entity)) {
      throw normaliseError(404, { detail: 'Not found' });
    }
    const { handleDashboardExport } = await import('./mock/handlers');
    return new Blob([handleDashboardExport(entity)], { type: 'text/csv;charset=utf-8' });
  }
  const token = getToken();
  const res = await fetch(buildUrl(`/dashboard/export/${entity}`), {
    method: 'GET',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    credentials: 'omit',
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw normaliseError(res.status, data);
  }
  return res.blob();
};
