import { useState } from 'react';
import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { DashboardListSection, OverviewPanel } from '@/components/dashboard';
import { useDashboardOverview } from '@/hooks/useDashboard';
import type { DashboardEntity } from '@/api/dashboard';

type TabKey = DashboardEntity | 'knowledge-gaps';

const TABS: Array<{ key: TabKey; label: string }> = [
  { key: 'documents', label: 'Documents' },
  { key: 'users', label: 'Users' },
  { key: 'audit', label: 'Audit' },
  { key: 'feedback', label: 'Feedback' },
  { key: 'knowledge-gaps', label: 'Knowledge gaps' },
];

export default function DashboardPage() {
  const { overview, loading, error, reload } = useDashboardOverview();
  const [activeTab, setActiveTab] = useState<TabKey>('documents');

  return (
    <div className="dashboard" data-testid="dashboard-page">
      <div className="dashboard-header">
        <h1>Dashboard</h1>
        <p>Tenant overview: questions, activity and knowledge gaps</p>
      </div>

      <section aria-label="Overview">
        {loading && (
          <div style={styles.center}>
            <Spinner label="Loading dashboard…" />
          </div>
        )}

        {!loading && error && (
          <div style={styles.errorBox}>
            <Alert style={styles.alert}>{error}</Alert>
            <Button type="button" variant="outline" size="sm" onClick={reload}>
              Retry
            </Button>
          </div>
        )}

        {!loading && !error && overview && <OverviewPanel overview={overview} />}
      </section>

      <section aria-label="Dashboard lists" style={styles.lists}>
        <div role="tablist" aria-label="Dashboard sections" style={styles.tabs}>
          {TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              role="tab"
              id={`dashboard-tab-${tab.key}`}
              aria-selected={activeTab === tab.key}
              aria-controls={`dashboard-panel-${tab.key}`}
              onClick={() => setActiveTab(tab.key)}
              style={{
                ...styles.tab,
                ...(activeTab === tab.key ? styles.tabActive : {}),
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div
          role="tabpanel"
          id={`dashboard-panel-${activeTab}`}
          aria-labelledby={`dashboard-tab-${activeTab}`}
          style={styles.panel}
        >
          <DashboardListSection key={activeTab} entity={activeTab} />
        </div>
      </section>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  center: { display: 'flex', justifyContent: 'center', padding: '32px 0' },
  errorBox: { marginBottom: '16px' },
  alert: { marginBottom: '12px' },
  lists: { marginTop: '24px' },
  tabs: {
    display: 'flex',
    gap: '4px',
    borderBottom: '1px solid #e2e8f0',
    marginBottom: '16px',
    flexWrap: 'wrap',
  },
  tab: {
    padding: '10px 16px',
    border: 'none',
    background: 'transparent',
    fontSize: '14px',
    fontWeight: 500,
    color: '#64748b',
    cursor: 'pointer',
    borderBottom: '2px solid transparent',
    borderRadius: '6px 6px 0 0',
  },
  tabActive: {
    color: '#2563eb',
    borderBottom: '2px solid #2563eb',
    fontWeight: 600,
  },
  panel: { minHeight: '240px' },
};
