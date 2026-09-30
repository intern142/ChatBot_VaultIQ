import { useAuth } from '../../context/AuthContext';
import { Button } from '../ui/Button';

interface HeaderProps {
  role: string | null;
  tenantId: string | null;
}

export function Header({ role, tenantId }: HeaderProps) {
  const { logout } = useAuth();

  const roleLabels: Record<string, string> = {
    super_admin: 'Super Admin',
    client_admin: 'Client Admin',
    employee: 'Employee',
  };

  const roleColors: Record<string, string> = {
    super_admin: '#fef3c7',
    client_admin: '#dbeafe',
    employee: '#fce7f3',
  };

  const roleTextColors: Record<string, string> = {
    super_admin: '#92400e',
    client_admin: '#1e40af',
    employee: '#9d174d',
  };

  const bg = roleColors[role || ''] || '#e2e8f0';
  const color = roleTextColors[role || ''] || '#334155';

  return (
    <header style={styles.header}>
      <div style={styles.left}>
        <h1 style={styles.title}>VaultIQ</h1>
        {tenantId && <span style={styles.tenant}>Tenant: {tenantId.slice(0, 8)}…</span>}
      </div>
      <div style={styles.right}>
        {role && (
          <span
            style={{
              ...styles.roleBadge,
              background: bg,
              color,
            }}
          >
            {roleLabels[role] || role}
          </span>
        )}
        <Button variant="ghost" onClick={logout} size="sm">
          Logout
        </Button>
      </div>
    </header>
  );
}

const styles: Record<string, React.CSSProperties> = {
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    height: '64px',
    padding: '0 24px',
    background: 'white',
    borderBottom: '1px solid #e2e8f0',
    position: 'sticky',
    top: 0,
    zIndex: 10,
  },
  left: { display: 'flex', alignItems: 'center', gap: '16px' },
  title: { margin: 0, fontSize: '20px', fontWeight: 700, color: '#0f172a' },
  tenant: { fontSize: '13px', color: '#64748b', background: '#f1f5f9', padding: '4px 10px', borderRadius: '6px' },
  right: { display: 'flex', alignItems: 'center', gap: '12px' },
  roleBadge: {
    padding: '4px 12px',
    borderRadius: '9999px',
    fontSize: '12px',
    fontWeight: 600,
  },
};