import { useAuth } from '../../context/AuthContext';
import { ShieldIcon, UsersIcon, FileTextIcon, BuildingIcon } from '../../components/Icons';

export function Dashboard() {
  const { user } = useAuth();

  const stats = [
    { label: 'Total Users', value: '0', icon: UsersIcon, color: 'var(--color-primary)' },
    { label: 'Organizations', value: '0', icon: BuildingIcon, color: '#2563eb' },
    { label: 'Active Users', value: '0', icon: UsersIcon, color: '#16a34a' },
    { label: 'Documents', value: '0', icon: FileTextIcon, color: '#ea580c' },
  ];

  const filteredStats = stats.filter(s => {
    if (user?.role === 'employee') return s.label === 'Documents' || s.label === 'Total Users';
    return true;
  });

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h1>Welcome back, {user?.name}</h1>
        <p>Here's an overview of your {user?.role === 'super_admin' ? 'system' : user?.role === 'client_admin' ? 'organization' : 'workspace'}</p>
      </div>

      <div className="stats-grid">
        {filteredStats.map((stat, index) => (
          <div key={index} className="stat-card">
            <div className="stat-icon" style={{ backgroundColor: `${stat.color}15`, color: stat.color }}>
              <stat.icon />
            </div>
            <div className="stat-content">
              <span className="stat-value">{stat.value}</span>
              <span className="stat-label">{stat.label}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="dashboard-sections">
        {user?.role === 'super_admin' && (
          <section className="dashboard-section">
            <h2>Quick Actions</h2>
            <div className="action-grid">
              <a href="/dashboard/tenants" className="action-card">
                <div className="action-icon"><BuildingIcon /></div>
                <span>Manage Tenants</span>
              </a>
              <a href="/dashboard/users" className="action-card">
                <div className="action-icon"><UsersIcon /></div>
                <span>Manage Users</span>
              </a>
              <a href="/dashboard/documents" className="action-card">
                <div className="action-icon"><FileTextIcon /></div>
                <span>View Documents</span>
              </a>
            </div>
          </section>
        )}

        {user?.role === 'client_admin' && (
          <section className="dashboard-section">
            <h2>Quick Actions</h2>
            <div className="action-grid">
              <a href="/dashboard/users" className="action-card">
                <div className="action-icon"><UsersIcon /></div>
                <span>Manage Team</span>
              </a>
              <a href="/dashboard/documents" className="action-card">
                <div className="action-icon"><FileTextIcon /></div>
                <span>Upload Documents</span>
              </a>
            </div>
          </section>
        )}

        {user?.role === 'employee' && (
          <section className="dashboard-section">
            <h2>Quick Actions</h2>
            <div className="action-grid">
              <a href="/dashboard/documents" className="action-card">
                <div className="action-icon"><FileTextIcon /></div>
                <span>View Documents</span>
              </a>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}