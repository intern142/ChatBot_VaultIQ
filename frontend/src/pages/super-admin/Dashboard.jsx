import { useAuth } from '../../context/AuthContext';

export default function Dashboard() {
  const { user } = useAuth();

  const stats = {
    totalUsers: 0,
    activeEmployees: 0,
    totalDocuments: 0,
    pendingApproval: 0,
    approvedDocuments: 0,
  };

  return (
    <div className="page">
      <div className="dashboard-header">
        <h1 className="dashboard-title">Welcome, {user?.name || 'Admin'}</h1>
      </div>

      <h2 className="section-title">Overview</h2>
      <div className="stats-grid">
        <div className="stat-card">
          <h3>Total Users</h3>
          <p className="stat-value">{stats.totalUsers}</p>
        </div>
        <div className="stat-card">
          <h3>Active Employees</h3>
          <p className="stat-value">{stats.activeEmployees}</p>
        </div>
        <div className="stat-card">
          <h3>Total Documents</h3>
          <p className="stat-value">{stats.totalDocuments}</p>
        </div>
        <div className="stat-card">
          <h3>Documents Pending Approval</h3>
          <p className="stat-value">{stats.pendingApproval}</p>
        </div>
        <div className="stat-card">
          <h3>Approved Documents</h3>
          <p className="stat-value">{stats.approvedDocuments}</p>
        </div>
      </div>

      <h2 className="section-title recent-title">Recent Activity</h2>
      <div className="empty-state">
        <p>No recent activity to display.</p>
      </div>
    </div>
  );
}
