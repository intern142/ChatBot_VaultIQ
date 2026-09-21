import { useAuth } from '../../context/AuthContext';

export default function Settings() {
  const { user } = useAuth();

  return (
    <div className="page">
      <h1>Settings</h1>
      <p className="page-placeholder">
        Configure platform-wide settings and preferences.
      </p>
      <div className="profile-card">
        <div className="form-group">
          <label>Platform Name</label>
          <input type="text" value="VaultIQ" readOnly />
        </div>
        <div className="form-group">
          <label>Admin Email</label>
          <input type="text" value={user?.email || ''} readOnly />
        </div>
        <div className="form-group">
          <label>Max Upload Size</label>
          <input type="text" value="20MB" readOnly />
        </div>
        <button className="primary-btn" disabled>Save Changes</button>
      </div>
    </div>
  );
}
