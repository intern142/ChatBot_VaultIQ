import { NavLink } from 'react-router-dom';

type Role = 'super_admin' | 'client_admin' | 'employee' | null;

interface SidebarProps {
  role: Role;
  tenantId: string | null;
}

function navLinkStyle(isActive: boolean): React.CSSProperties {
  return {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '12px 16px',
    borderRadius: '8px',
    color: isActive ? 'white' : '#94a3b8',
    textDecoration: 'none',
    fontSize: '14px',
    fontWeight: isActive ? 600 : 400,
    background: isActive ? '#334155' : 'transparent',
    transition: 'background 0.15s, color 0.15s',
  };
}

const styles: Record<string, React.CSSProperties> = {
  sidebar: {
    width: '260px',
    background: '#1e293b',
    color: 'white',
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    position: 'sticky',
    top: 0,
    borderRight: '1px solid #334155',
  },
  brand: {
    padding: '20px 24px',
    borderBottom: '1px solid #334155',
  },
  logo: {
    fontSize: '22px',
    fontWeight: 700,
    letterSpacing: '-0.5px',
  },
  nav: { flex: 1, padding: '16px 12px', overflowY: 'auto' },
  list: { listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '4px' },
  navLinkActive: {},
  icon: { fontSize: '16px' },
  footer: { padding: '16px', borderTop: '1px solid #334155' },
  tenantBadge: {
    display: 'inline-block',
    padding: '4px 10px',
    borderRadius: '9999px',
    fontSize: '11px',
    fontWeight: 600,
    background: '#334155',
    color: '#94a3b8',
  },
};

export function Sidebar({ role, tenantId }: SidebarProps) {
  const operatorNav = [
    { path: '/admin/tenants', label: 'Tenants', icon: '🏢' },
  ];

  const tenantNav = [
    { path: '/documents', label: 'Documents', icon: '📄' },
    { path: '/storage', label: 'Storage', icon: '💾' },
  ];

  const clientAdminNav = [{ path: '/dashboard', label: 'Dashboard', icon: '📊' }];

  return (
    <aside style={styles.sidebar} role="navigation" aria-label="Main navigation">
      <div style={styles.brand}>
        <span style={styles.logo}>VaultIQ</span>
      </div>
      <nav style={styles.nav}>
        {role === 'super_admin' && (
          <ul style={styles.list}>
            {operatorNav.map((item) => (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  style={({ isActive }) => ({
                    ...navLinkStyle(isActive),
                    ...(isActive ? styles.navLinkActive : {}),
                  })}
                >
                  <span style={styles.icon}>{item.icon}</span>
                  <span>{item.label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        )}
        {(role === 'client_admin' || role === 'employee') && (
          <ul style={styles.list}>
            {role === 'client_admin' &&
              clientAdminNav.map((item) => (
                <li key={item.path}>
                  <NavLink
                    to={item.path}
                    style={({ isActive }) => ({
                      ...navLinkStyle(isActive),
                      ...(isActive ? styles.navLinkActive : {}),
                    })}
                  >
                    <span style={styles.icon}>{item.icon}</span>
                    <span>{item.label}</span>
                  </NavLink>
                </li>
              ))}
            {tenantNav.map((item) => (
              <li key={item.path}>
                <NavLink
                  to={item.path}
                  style={({ isActive }) => ({
                    ...navLinkStyle(isActive),
                    ...(isActive ? styles.navLinkActive : {}),
                  })}
                >
                  <span style={styles.icon}>{item.icon}</span>
                  <span>{item.label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        )}
      </nav>
      <div style={styles.footer}>
        {tenantId && (
          <span style={styles.tenantBadge}>
            Tenant: {tenantId.slice(0, 8)}…
          </span>
        )}
      </div>
    </aside>
  );
}