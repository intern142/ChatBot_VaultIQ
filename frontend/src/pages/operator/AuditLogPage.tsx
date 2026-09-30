import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { getTenantAudit } from '../../api/admin';
import { Button } from '../../components/ui/Button';
import { Spinner } from '../../components/ui/Spinner';
import { Alert } from '../../components/ui/Alert';
import { EmptyState } from '../../components/ui/EmptyState';
import { PATHS } from '../../routes/paths';
import { Link } from 'react-router-dom';

interface AuditEntry {
  id: string;
  actor_user_id: string | null;
  actor_role: string;
  action: string;
  target_type: string;
  target_id: string;
  details: Record<string, unknown>;
  created_at: string;
}

export default function AuditLogPage() {
  const { tenantId } = useParams<{ tenantId: string }>();
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!tenantId) return;
    let mounted = true;
    getTenantAudit(tenantId)
      .then((data) => {
        if (mounted) setEntries(data);
      })
      .catch((err: any) => {
        if (mounted) setError(err.message);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => { mounted = false; };
  }, [tenantId]);

  const formatDate = (iso: string) => new Date(iso).toLocaleString();

  if (loading) {
    return (
      <div style={styles.center}>
        <Spinner size="lg" />
        <span>Loading audit log…</span>
      </div>
    );
  }

  if (error) {
    return <Alert variant="error">{error}</Alert>;
  }

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <Link to={PATHS.tenants}>
          <Button variant="outline">← Back to Tenants</Button>
        </Link>
        <div>
          <h1 style={styles.title}>Audit Log</h1>
          <p style={styles.subtitle}>Tenant: {tenantId}</p>
        </div>
      </div>

      {entries.length === 0 ? (
        <EmptyState icon="📋" title="No audit entries" description="No actions recorded for this tenant yet" />
      ) : (
        <div style={styles.tableWrapper}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Time</th>
                <th style={styles.th}>Actor</th>
                <th style={styles.th}>Role</th>
                <th style={styles.th}>Action</th>
                <th style={styles.th}>Target</th>
                <th style={styles.th}>Details</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id}>
                  <td style={styles.td}>{formatDate(e.created_at)}</td>
                  <td style={styles.td}>{e.actor_user_id || 'system'}</td>
                  <td style={styles.td}><span style={styles.badge}>{e.actor_role}</span></td>
                  <td style={styles.td}>{e.action}</td>
                  <td style={styles.td}>{e.target_type}: {e.target_id.slice(0, 8)}…</td>
                  <td style={styles.td}><pre style={styles.pre}>{JSON.stringify(e.details, null, 2)}</pre></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {entries.length >= 500 && (
        <p style={styles.capNote}>Showing latest 500 entries (capped by backend)</p>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { padding: '24px', maxWidth: '1200px', margin: '0 auto' },
  header: {
    display: 'flex',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    marginBottom: '24px',
    gap: '16px',
  },
  title: { margin: '0 0 4px', fontSize: '24px', fontWeight: 700, color: '#0f172a' },
  subtitle: { margin: 0, fontSize: '14px', color: '#64748b' },
  center: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '300px',
    gap: '12px',
    color: '#64748b',
  },
  tableWrapper: { overflowX: 'auto' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '13px' },
  th: {
    textAlign: 'left',
    padding: '10px 12px',
    borderBottom: '2px solid #e2e8f0',
    fontWeight: 600,
    color: '#334155',
    whiteSpace: 'nowrap',
  },
  td: {
    padding: '10px 12px',
    borderBottom: '1px solid #e2e8f0',
    color: '#1e293b',
    whiteSpace: 'nowrap',
  },
  badge: {
    display: 'inline-block',
    padding: '2px 8px',
    borderRadius: '9999px',
    fontSize: '11px',
    fontWeight: 600,
    background: '#e2e8f0',
    color: '#334155',
  },
  pre: { margin: 0, fontSize: '11px', maxWidth: '300px', overflow: 'auto' },
  capNote: { marginTop: '16px', fontSize: '12px', color: '#94a3b8', fontStyle: 'italic' },
};