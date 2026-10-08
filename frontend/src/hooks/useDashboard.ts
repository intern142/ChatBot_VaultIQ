import { useCallback, useEffect, useState } from 'react';
import {
  downloadDashboardCsv,
  getDashboardList,
  getDashboardOverview,
  getKnowledgeGaps,
} from '@/api/dashboard';
import type { DashboardEntity } from '@/api/dashboard';
import { ApiError } from '@/api/errors';
import type { OverviewResponse, PaginatedResponse } from '@/api/types';

export const DASHBOARD_404_MESSAGE =
  'Dashboard data is unavailable: the server returned 404 Not Found. The dashboard API is not mounted on this backend build (tracked in FRESH.md Phase 8).';

export function dashboardErrorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return 'Your session has expired. Please sign in again.';
    if (err.status === 403) return 'You do not have permission to view dashboard data.';
    if (err.status === 404) return DASHBOARD_404_MESSAGE;
    if (err.message) return err.message;
    return 'Failed to load dashboard data.';
  }
  if (err instanceof Error && err.message) return err.message;
  return 'Failed to load dashboard data.';
}

export interface UseDashboardOverviewResult {
  overview: OverviewResponse | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useDashboardOverview(): UseDashboardOverviewResult {
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getDashboardOverview()
      .then((data) => {
        if (!cancelled) setOverview(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setOverview(null);
          setError(dashboardErrorMessage(err));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tick]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { overview, loading, error, reload };
}

export type DashboardListEntity = DashboardEntity | 'knowledge-gaps';

export interface UseDashboardListResult {
  items: Array<Record<string, unknown>>;
  total: number;
  limit: number;
  offset: number;
  search: string;
  loading: boolean;
  error: string | null;
  runSearch: (value: string) => void;
  goToOffset: (value: number) => void;
  reload: () => void;
}

export function useDashboardList(
  entity: DashboardListEntity,
  limit = 10,
): UseDashboardListResult {
  const [data, setData] = useState<PaginatedResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const params = { limit, offset, ...(search ? { search } : {}) };
    const request =
      entity === 'knowledge-gaps' ? getKnowledgeGaps(params) : getDashboardList(entity, params);
    request
      .then((data) => {
        if (!cancelled) setData(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setData(null);
          setError(dashboardErrorMessage(err));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [entity, limit, offset, search, tick]);

  const runSearch = useCallback((value: string) => {
    setOffset(0);
    setSearch(value);
  }, []);
  const goToOffset = useCallback((value: number) => setOffset(Math.max(0, value)), []);
  const reload = useCallback(() => setTick((t) => t + 1), []);

  return {
    items: data?.items ?? [],
    total: data?.total ?? 0,
    limit,
    offset,
    search,
    loading,
    error,
    runSearch,
    goToOffset,
    reload,
  };
}

export interface UseDashboardExportResult {
  exporting: string | null;
  error: string | null;
  exportCsv: (entity: DashboardEntity) => Promise<boolean>;
  dismissError: () => void;
}

function triggerBrowserDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function useDashboardExport(): UseDashboardExportResult {
  const [exporting, setExporting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const exportCsv = useCallback(async (entity: DashboardEntity): Promise<boolean> => {
    setExporting(entity);
    setError(null);
    try {
      const blob = await downloadDashboardCsv(entity);
      triggerBrowserDownload(blob, `${entity}.csv`);
      return true;
    } catch (err: unknown) {
      setError(dashboardErrorMessage(err));
      return false;
    } finally {
      setExporting(null);
    }
  }, []);

  const dismissError = useCallback(() => setError(null), []);
  return { exporting, error, exportCsv, dismissError };
}
