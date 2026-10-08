import type { OverviewResponse } from '@/api/types';

interface OverviewPanelProps {
  overview: OverviewResponse;
}

interface StatCard {
  label: string;
  value: string;
  hint: string;
  color: string;
}

function formatConfidence(value: number | null): string {
  if (value === null) return '—';
  return value.toFixed(2);
}

function buildCards(overview: OverviewResponse): StatCard[] {
  return [
    {
      label: 'Active users',
      value: String(overview.active_users),
      hint: 'Users active in this period',
      color: '#16a34a',
    },
    {
      label: 'Answered',
      value: String(overview.answered_count),
      hint: 'Questions fully answered',
      color: '#2563eb',
    },
    {
      label: 'Partial',
      value: String(overview.partial_count),
      hint: 'Questions partially answered',
      color: '#ea580c',
    },
    {
      label: 'Not found',
      value: String(overview.not_found_count),
      hint: 'Questions with no answer found',
      color: '#dc2626',
    },
    {
      label: 'Avg confidence',
      value: formatConfidence(overview.avg_confidence),
      hint: 'Average answer confidence',
      color: '#7c3aed',
    },
  ];
}

type DayCount = { day: string; count: number };

function isDayCount(value: unknown): value is DayCount {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as { day?: unknown; count?: unknown };
  return typeof candidate.day === 'string' && typeof candidate.count === 'number';
}

export function OverviewPanel({ overview }: OverviewPanelProps) {
  const cards = buildCards(overview);
  const series = overview.questions_per_day_30d.filter(isDayCount);
  const maxCount = series.reduce((max, entry) => Math.max(max, entry.count), 0);

  return (
    <div>
      <div className="stats-grid" data-testid="dashboard-stats">
        {cards.map((card) => (
          <div className="stat-card" key={card.label}>
            <div
              className="stat-icon"
              style={{ backgroundColor: `${card.color}15`, color: card.color }}
            >
              <span aria-hidden="true">●</span>
            </div>
            <div className="stat-content">
              <span className="stat-value">{card.value}</span>
              <span className="stat-label">{card.label}</span>
            </div>
          </div>
        ))}
      </div>

      <section className="dashboard-section" data-testid="questions-per-day">
        <h2>Questions per day (last 30 days)</h2>
        {series.length === 0 ? (
          <p style={styles.muted}>No question activity recorded in the last 30 days.</p>
        ) : (
          <div style={styles.chart} role="img" aria-label="Questions per day bar chart">
            {series.map((entry) => (
              <div key={entry.day} style={styles.barWrap} title={`${entry.day}: ${entry.count}`}>
                <div
                  style={{
                    ...styles.bar,
                    height: `${maxCount > 0 ? Math.max((entry.count / maxCount) * 100, 2) : 2}%`,
                  }}
                />
                <span style={styles.barValue}>{entry.count}</span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  muted: { color: '#94a3b8', fontSize: '14px', margin: '8px 0 16px' },
  chart: {
    display: 'flex',
    alignItems: 'flex-end',
    gap: '4px',
    height: '140px',
    padding: '12px 0 4px',
  },
  barWrap: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'flex-end',
    height: '100%',
    minWidth: 0,
  },
  bar: {
    width: '100%',
    maxWidth: '28px',
    backgroundColor: '#2563eb',
    borderRadius: '3px 3px 0 0',
    minHeight: '2px',
  },
  barValue: { fontSize: '10px', color: '#64748b', marginTop: '4px' },
};
