import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { useAuth } from '../../context/AuthContext';

export function AppShell() {
  const { role, tenantId } = useAuth();

  return (
    <div style={styles.shell}>
      <Sidebar role={role} tenantId={tenantId} />
      <div style={styles.main}>
        <Header role={role} tenantId={tenantId} />
        <main style={styles.content}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  shell: { display: 'flex', minHeight: '100vh' },
  main: { flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 },
  content: { flex: 1, padding: '24px', overflow: 'auto' },
};