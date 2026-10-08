import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import DashboardPage from '@/pages/DashboardPage';
import { DASHBOARD_404_MESSAGE } from '@/hooks/useDashboard';
import { getDashboardOverview, getDashboardList } from '@/api/dashboard';
import { ApiError } from '@/api/errors';
import type { OverviewResponse, PaginatedResponse } from '@/api/types';

vi.mock('@/api/dashboard', () => ({
  getDashboardOverview: vi.fn(),
  getDashboardList: vi.fn(),
  getKnowledgeGaps: vi.fn(),
  downloadDashboardCsv: vi.fn(),
}));

const overviewFixture: OverviewResponse = {
  questions_per_day_30d: [
    { day: '2026-10-01', count: 3 },
    { day: '2026-10-02', count: 0 },
  ],
  active_users: 4,
  answered_count: 9,
  partial_count: 2,
  not_found_count: 1,
  avg_confidence: 0.71,
};

const documentsFixture: PaginatedResponse = {
  items: [
    {
      id: 'doc-1',
      original_filename: 'policy.pdf',
      category: 'policy',
      status: 'approved',
      processing_status: 'ready',
      size_bytes: 2048,
      created_at: '2026-10-01T00:00:00Z',
    },
  ],
  total: 1,
  limit: 10,
  offset: 0,
};

const usersFixture: PaginatedResponse = {
  items: [{ id: 'user-1', email: 'admin@acme.test', role: 'client_admin', is_active: true }],
  total: 1,
  limit: 10,
  offset: 0,
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getDashboardOverview).mockResolvedValue(overviewFixture);
  vi.mocked(getDashboardList).mockImplementation(async (entity) => {
    if (entity === 'users') return usersFixture;
    return documentsFixture;
  });
});

describe('DashboardPage', () => {
  it('shows a loading state, then renders overview figures and the active list', async () => {
    let resolveOverview: (value: OverviewResponse) => void = () => undefined;
    vi.mocked(getDashboardOverview).mockReturnValue(
      new Promise<OverviewResponse>((resolve) => {
        resolveOverview = resolve;
      }),
    );

    render(<DashboardPage />);
    expect(screen.getByText('Loading dashboard…')).toBeInTheDocument();

    resolveOverview(overviewFixture);
    await waitFor(() => expect(screen.getByText('Active users')).toBeInTheDocument());
    expect(screen.getByText('4')).toBeInTheDocument();
    expect(screen.getByText('9')).toBeInTheDocument();
    expect(screen.getByText('0.71')).toBeInTheDocument();
    expect(screen.getByTestId('questions-per-day')).toBeInTheDocument();
    expect(await screen.findByText('policy.pdf')).toBeInTheDocument();
  });

  it('renders each overview figure label', async () => {
    render(<DashboardPage />);
    for (const label of ['Active users', 'Answered', 'Partial', 'Not found', 'Avg confidence']) {
      expect(await screen.findByText(label)).toBeInTheDocument();
    }
  });

  it('shows the 404 blocker message with a retry action when the API is missing', async () => {
    vi.mocked(getDashboardOverview).mockRejectedValue(new ApiError('Not Found', 404));
    vi.mocked(getDashboardList).mockRejectedValue(new ApiError('Not Found', 404));

    render(<DashboardPage />);
    expect((await screen.findAllByText(DASHBOARD_404_MESSAGE)).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Retry').length).toBeGreaterThan(0);
    expect(screen.queryByTestId('dashboard-stats')).not.toBeInTheDocument();
  });

  it('maps a 403 failure to a permission message', async () => {
    vi.mocked(getDashboardOverview).mockRejectedValue(new ApiError('Forbidden', 403));
    vi.mocked(getDashboardList).mockRejectedValue(new ApiError('Forbidden', 403));

    render(<DashboardPage />);
    expect(
      (await screen.findAllByText('You do not have permission to view dashboard data.')).length,
    ).toBeGreaterThan(0);
  });

  it('shows an empty state when the list has no rows', async () => {
    vi.mocked(getDashboardList).mockResolvedValue({ items: [], total: 0, limit: 10, offset: 0 });
    render(<DashboardPage />);
    expect(await screen.findByText('No documents yet')).toBeInTheDocument();
  });

  it('switches tabs and fetches the selected entity', async () => {
    render(<DashboardPage />);
    await screen.findByText('policy.pdf');

    fireEvent.click(screen.getByRole('tab', { name: 'Users' }));
    expect(await screen.findByText('admin@acme.test')).toBeInTheDocument();
    expect(getDashboardList).toHaveBeenLastCalledWith('users', { limit: 10, offset: 0 });
    expect(screen.getByRole('tab', { name: 'Users' })).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tab', { name: 'Documents' })).toHaveAttribute(
      'aria-selected',
      'false',
    );
  });

  it('filters the list from a search submission', async () => {
    render(<DashboardPage />);
    await screen.findByText('policy.pdf');

    fireEvent.change(screen.getByLabelText('Search Documents'), {
      target: { value: 'policy' },
    });
    fireEvent.submit(screen.getByRole('search'));

    await waitFor(() =>
      expect(getDashboardList).toHaveBeenLastCalledWith('documents', {
        limit: 10,
        offset: 0,
        search: 'policy',
      }),
    );
  });
});
