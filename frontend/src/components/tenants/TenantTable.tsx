import { Button } from '../ui/Button';
import { Spinner } from '../ui/Spinner';
import { formatDate } from '../../utils/format';
import { Link } from 'react-router-dom';

interface TenantTableProps {
  tenants: Array<{
    id: string;
    short_code: string;
    name: string;
    status: string;
    storage_quota_mb: number | null;
    created_at: string;
  }>;
  onSuspend: (id: string) => void;
  onReactivate: (id: string) => void;
  onInvite: (tenant: { id: string; name: string }) => void;
  loading?: boolean;
}

export function TenantTable({ tenants, onSuspend, onReactivate, onInvite, loading }: TenantTableProps) {

  const handleSuspend = (id: string) => {
    if (!window.confirm('Suspend this tenant? All user sessions will be revoked immediately.')) return;
    onSuspend(id);
  };

  const handleReactivate = (id: string) => {
    if (!window.confirm('Reactivate this tenant?')) return;
    onReactivate(id);
  };

  const handleInvite = (tenant: { id: string; name: string }) => {
    onInvite(tenant);
  };

  if (loading) {
    return (
      <div style={styles.loading}>
        <Spinner size="lg" />
        <span>Loading tenants…</span>
      </div>
    );
  }

  return (
    <div style={styles.tableWrapper}>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>Code</th>
            <th style={styles.th}>Name</th>
            <th style={styles.th}>Status</th>
            <th style={styles.th}>Quota</th>
            <th style={styles.th}>Created</th>
            <th style={styles.thActions}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {tenants.map((tenant) => (
            <tr key={tenant.id} style={styles.tr}>
              <td style={styles.td}>
                <Link to={`/admin/tenants/${tenant.id}/audit`} style={styles.codeLink}>
                  {tenant.short_code}
                </Link>
              </td>
              <td style={styles.td}>{tenant.name}</td>
              <td style={styles.td}>
                <span style={{ ...styles.badge, background: statusColor(tenant.status) }}>
                  {tenant.status}
                </span>
              </td>
              <td style={styles.td}>
                {tenant.storage_quota_mb ? `${tenant.storage_quota_mb} MB` : 'Unlimited'}
              </td>
              <td style={styles.td}>{formatDate(tenant.created_at)}</td>
              <td style={styles.tdActions}>
                <div style={styles.actions}>
                  <Link to={`/admin/tenants/${tenant.id}/audit`}>
                    <Button variant="ghost" size="sm">Audit</Button>
                  </Link>
                  {tenant.status === 'active' && (
                    <>
                      <Button variant="ghost" size="sm" onClick={() => handleInvite(tenant)}>
                        Invite
                      </Button>
                      <Button variant="danger" size="sm" onClick={() => handleSuspend(tenant.id)}>
                        Suspend
                      </Button>
                    </>
                  )}
                  {tenant.status === 'suspended' && (
                    <Button variant="ghost" size="sm" onClick={() => handleReactivate(tenant.id)}>
                      Reactivate
                    </Button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function statusColor(status: string) {
  switch (status) {
    case 'active': return '#dcfce7';
    case 'suspended': return '#fef2f2';
    case 'offboarding': return '#fef3c7';
    case 'purged': return '#f3f4f6';
    default: return '#e2e8f0';
  }
}

const styles: Record<string, React.CSSProperties> = {
  tableWrapper: { overflowX: 'auto' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '13px' },
  th: {
    textAlign: 'left',
    padding: '12px 16px',
    borderBottom: '2px solid #e2e8f0',
    fontWeight: 600,
    color: '#334155',
    whiteSpace: 'nowrap',
  },
  thActions: { textAlign: 'right', padding: '12px 16px' },
  tr: { borderBottom: '1px solid #e2e8f0' },
  td: { padding: '12px 16px', color: '#1e293b', whiteSpace: 'nowrap' },
  tdActions: { textAlign: 'right', padding: '12px 16px' },
  codeLink: { fontWeight: 600, color: '#1e293b', textDecoration: 'none' },
  badge: { display: 'inline-block', padding: '2px 8px', borderRadius: '9999px', fontSize: '11px', fontWeight: 600, color: '#1e293b' },
  actions: { display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '8px' },
  loading: { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px', padding: '48px', color: '#64748b' },
};