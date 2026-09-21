import { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { authApi } from '../../api/auth';

export default function Dashboard() {
  const { user } = useAuth();
  const [stats, setStats] = useState({
    totalUsers: 0,
    totalOrganizations: 0,
    activeUsers: 0,
    totalDocuments: 0,
    pendingApproval: 0,
    approvedDocuments: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchStats() {
      try {
        const data = await authApi.getSuperAdminStats();
        setStats(data);
      } catch (e) {
        console.error('Failed to fetch super admin stats:', e);
      } finally {
        setLoading(false);
      }
    }
    fetchStats();
  }, []);

  if (loading) {
    return (
      <div className="page">
        <div className="dashboard-header">
          <h1 className="dashboard-title">Welcome, {user?.name || 'Admin'}</h1>
        </div>
        <h2 className="section-title">Overview</h2>
        <div className="stats-grid">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="stat-card">
              <h3>Loading...</h3>
              <p className="stat-value"><span className="pulse">—</span></p>
            </div>
          ))}
        </div>
      </div>
    );
  }

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
          <h3>Total Organizations</h3>
          <p className="stat-value">{stats.totalOrganizations}</p>
        </div>
        <div className="stat-card">
          <h3>Active Users</h3>
          <p className="stat-value">{stats.activeUsers}</p>
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
