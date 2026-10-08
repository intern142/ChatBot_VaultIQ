import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import {
  useDashboardOverview,
  useDashboardList,
  useDashboardExport,
} from '@/hooks/useDashboard';
import { DASHBOARD_404_MESSAGE } from '@/hooks/useDashboard';
import {
  getDashboardOverview,
  getDashboardList,
  getKnowledgeGaps,
  downloadDashboardCsv,
} from '@/api/dashboard';
import { ApiError } from '@/api/errors';
import type { OverviewResponse, PaginatedResponse } from '@/api/types';

vi.mock('@/api/dashboard', () => ({
  getDashboardOverview: vi.fn(),
  getDashboardList: vi.fn(),
  getKnowledgeGaps: vi.fn(),
  downloadDashboardCsv: vi.fn(),
}));

const overviewFixture: OverviewResponse = {
  questions_per_day_30d: [{ day: '2026-10-01', count: 2 }],
  active_users: 4,
  answered_count: 9,
  partial_count: 2,
  not_found_count: 1,
  avg_confidence: 0.71,
};

const listFixture: PaginatedResponse = {
  items: [{ id: 'row-1', email: 'a@b.test' }],
  total: 11,
  limit: 10,
  offset: 0,
};

beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useDashboardOverview', () => {
  it('loads the overview and exposes it', async () => {
    vi.mocked(getDashboardOverview).mockResolvedValue(overviewFixture);
    const { result } = renderHook(() => useDashboardOverview());
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBeNull();
    expect(result.current.overview?.active_users).toBe(4);
    expect(result.current.overview?.avg_confidence).toBe(0.71);
  });

  it('maps a 401 failure to a session-expired message', async () => {
    vi.mocked(getDashboardOverview).mockRejectedValue(new ApiError('Unauthorized', 401));
    const { result } = renderHook(() => useDashboardOverview());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.overview).toBeNull();
    expect(result.current.error).toBe('Your session has expired. Please sign in again.');
  });

  it('maps a 403 failure to a permission message', async () => {
    vi.mocked(getDashboardOverview).mockRejectedValue(new ApiError('Forbidden', 403));
    const { result } = renderHook(() => useDashboardOverview());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe('You do not have permission to view dashboard data.');
  });

  it('maps a 404 failure to the documented blocker message', async () => {
    vi.mocked(getDashboardOverview).mockRejectedValue(new ApiError('Not Found', 404));
    const { result } = renderHook(() => useDashboardOverview());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe(DASHBOARD_404_MESSAGE);
  });

  it('reloads on demand after a failure', async () => {
    vi.mocked(getDashboardOverview).mockRejectedValueOnce(new ApiError('boom', 500));
    const { result } = renderHook(() => useDashboardOverview());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe('boom');

    vi.mocked(getDashboardOverview).mockResolvedValueOnce(overviewFixture);
    act(() => result.current.reload());
    await waitFor(() => expect(result.current.overview).not.toBeNull());
    expect(result.current.error).toBeNull();
  });
});

describe('useDashboardList', () => {
  it('loads a list with default limit/offset', async () => {
    vi.mocked(getDashboardList).mockResolvedValue(listFixture);
    const { result } = renderHook(() => useDashboardList('users'));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(getDashboardList).toHaveBeenCalledWith('users', { limit: 10, offset: 0 });
    expect(result.current.items).toHaveLength(1);
    expect(result.current.total).toBe(11);
  });

  it('keeps knowledge-gaps on its own endpoint', async () => {
    vi.mocked(getKnowledgeGaps).mockResolvedValue({ items: [], total: 0, limit: 10, offset: 0 });
    const { result } = renderHook(() => useDashboardList('knowledge-gaps'));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(getKnowledgeGaps).toHaveBeenCalledWith({ limit: 10, offset: 0 });
    expect(getDashboardList).not.toHaveBeenCalled();
  });

  it('runs a search from offset 0 and includes it in the request', async () => {
    vi.mocked(getDashboardList).mockResolvedValue(listFixture);
    const { result } = renderHook(() => useDashboardList('documents'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => result.current.runSearch('policy'));
    await waitFor(() =>
      expect(getDashboardList).toHaveBeenLastCalledWith('documents', {
        limit: 10,
        offset: 0,
        search: 'policy',
      }),
    );
    expect(result.current.search).toBe('policy');
    expect(result.current.offset).toBe(0);
  });

  it('pages forward with goToOffset', async () => {
    vi.mocked(getDashboardList).mockResolvedValue(listFixture);
    const { result } = renderHook(() => useDashboardList('audit'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    act(() => result.current.goToOffset(10));
    await waitFor(() =>
      expect(getDashboardList).toHaveBeenLastCalledWith('audit', { limit: 10, offset: 10 }),
    );
  });

  it('clears the list and reports a mapped error on failure', async () => {
    vi.mocked(getDashboardList).mockRejectedValue(new ApiError('Forbidden', 403));
    const { result } = renderHook(() => useDashboardList('feedback'));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.items).toHaveLength(0);
    expect(result.current.error).toBe('You do not have permission to view dashboard data.');
  });

  it('maps a 404 list failure to the documented blocker message', async () => {
    vi.mocked(getDashboardList).mockRejectedValue(new ApiError('Not Found', 404));
    const { result } = renderHook(() => useDashboardList('documents'));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.error).toBe(DASHBOARD_404_MESSAGE);
  });
});

describe('useDashboardExport', () => {
  it('downloads a CSV blob and triggers the browser download', async () => {
    const createObjectURL = vi.fn(() => 'blob:mock');
    const revokeObjectURL = vi.fn();
    URL.createObjectURL = createObjectURL;
    URL.revokeObjectURL = revokeObjectURL;
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => undefined);
    vi.mocked(downloadDashboardCsv).mockResolvedValue(new Blob(['a,b\n1,2\n']));

    const { result } = renderHook(() => useDashboardExport());
    let ok = false;
    await act(async () => {
      ok = await result.current.exportCsv('users');
    });

    expect(ok).toBe(true);
    expect(downloadDashboardCsv).toHaveBeenCalledWith('users');
    expect(createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock');
    expect(result.current.exporting).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('reports a mapped error and does not download when the export fails', async () => {
    vi.mocked(downloadDashboardCsv).mockRejectedValue(new ApiError('Not Found', 404));
    const { result } = renderHook(() => useDashboardExport());
    let ok = true;
    await act(async () => {
      ok = await result.current.exportCsv('documents');
    });

    expect(ok).toBe(false);
    expect(result.current.error).toBe(DASHBOARD_404_MESSAGE);
    expect(result.current.exporting).toBeNull();
  });

  it('dismisses the export error', async () => {
    vi.mocked(downloadDashboardCsv).mockRejectedValue(new ApiError('Forbidden', 403));
    const { result } = renderHook(() => useDashboardExport());
    await act(async () => {
      await result.current.exportCsv('audit');
    });
    expect(result.current.error).toBe('You do not have permission to view dashboard data.');
    act(() => result.current.dismissError());
    expect(result.current.error).toBeNull();
  });
});
