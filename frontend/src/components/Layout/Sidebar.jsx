import { NavLink } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import {
  DashboardIcon,
  ChatIcon,
  HistoryIcon,
  DocumentsIcon,
  StaffIcon,
  SettingsIcon,
  TenantsIcon,
  HealthIcon,
  LogoutIcon,
  LogoMark,
} from '../Icons';

const employeeLinks = [
  {
    path: '/employee/dashboard',
    label: 'Dashboard',
    icon: DashboardIcon,
  },
  { path: '/employee/chat', label: 'Chat', icon: ChatIcon },
  { path: '/employee/history', label: 'History', icon: HistoryIcon },
];

const clientAdminLinks = [
  { path: '/admin/dashboard', label: 'Dashboard', icon: DashboardIcon },
  { path: '/admin/documents', label: 'Documents', icon: DocumentsIcon },
  { path: '/admin/staff', label: 'Staff', icon: StaffIcon },
  { path: '/admin/settings', label: 'Settings', icon: SettingsIcon },
];

const superAdminLinks = [
  { path: '/super/dashboard', label: 'Dashboard', icon: DashboardIcon },
  { path: '/super/documents', label: 'Documents Upload', icon: DocumentsIcon },
  { path: '/super/tenants', label: 'Staff / Tenants', icon: TenantsIcon },
  { path: '/super/health', label: 'Platform Health', icon: HealthIcon },
  { path: '/super/settings', label: 'Settings', icon: SettingsIcon },
];

const linksByRole = {
  employee: employeeLinks,
  'client-admin': clientAdminLinks,
  'super-admin': superAdminLinks,
};

const roleLabels = {
  employee: 'Employee',
  'client-admin': 'Client Admin',
  'super-admin': 'Super Admin',
};

export default function Sidebar() {
  const { role, logout } = useAuth();

  const links = linksByRole[role] || [];

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <span className="logo-mark">
          <LogoMark />
        </span>
        <div>
          <h2 className="logo">VaultIQ</h2>
          <span className="role-badge">{roleLabels[role] || role}</span>
        </div>
      </div>

      <nav className="sidebar-nav" aria-label="Primary">
        {links.map((link) => (
          <NavLink
            key={link.path}
            to={link.path}
            className={({ isActive }) =>
              `nav-link ${isActive ? 'active' : ''}`
            }
            title={link.label}
          >
            <span className="nav-icon">
              <link.icon />
            </span>
            <span className="nav-label">{link.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="sidebar-footer">
        <button type="button" onClick={logout} className="logout-btn">
          <LogoutIcon />
          <span className="nav-label">Logout</span>
        </button>
      </div>
    </aside>
  );
}