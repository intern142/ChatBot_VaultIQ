import { NavLink, Outlet } from 'react-router-dom';
import { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import {
  HomeIcon,
  UsersIcon,
  FileTextIcon,
  LogOutIcon,
  MenuIcon,
  XIcon,
  ChevronRightIcon,
  BuildingIcon,
} from '../../components/Icons';

export function Layout() {
  const { user, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: HomeIcon, roles: ['super_admin', 'client_admin', 'employee'] },
    { path: '/dashboard/tenants', label: 'Tenants', icon: BuildingIcon, roles: ['super_admin'] },
    { path: '/dashboard/users', label: 'Users', icon: UsersIcon, roles: ['super_admin', 'client_admin'] },
    { path: '/dashboard/documents', label: 'Documents', icon: FileTextIcon, roles: ['super_admin', 'client_admin'] },
  ];

  const filteredNavItems = navItems.filter(item => item.roles.includes(user?.role ?? ''));

  return (
    <div className="layout">
      <aside className={`sidebar ${mobileMenuOpen ? 'mobile-open' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-brand">
            <BuildingIcon />
            <span>VaultIQ</span>
          </div>
          <button
            className="sidebar-close"
            onClick={() => setMobileMenuOpen(false)}
            aria-label="Close sidebar"
          >
            <XIcon />
          </button>
        </div>
        <nav className="sidebar-nav">
          {filteredNavItems.map(item => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
              onClick={() => setMobileMenuOpen(false)}
            >
              <item.icon />
              <span>{item.label}</span>
              {item.path === '/dashboard/tenants' && user?.role === 'super_admin' && <ChevronRightIcon />}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="user-info">
            <div className="user-avatar">
              {user?.name?.charAt(0).toUpperCase()}
            </div>
            <div className="user-details">
              <span className="user-name">{user?.name}</span>
              <span className="user-role">{user?.role?.replace('_', ' ')}</span>
            </div>
          </div>
          <button className="btn btn-secondary btn-sm logout-btn" onClick={logout}>
            <LogOutIcon />
            <span>Logout</span>
          </button>
        </div>
      </aside>

      <div className="main-wrapper">
        <header className="topbar">
          <button
            className="mobile-menu-btn"
            onClick={() => setMobileMenuOpen(true)}
            aria-label="Open menu"
          >
            <MenuIcon />
          </button>
          <div className="topbar-title">
            <h1>{getPageTitle()}</h1>
          </div>
        </header>

        <main className="content">
          <Outlet />
        </main>
      </div>

      {mobileMenuOpen && (
        <div className="sidebar-overlay" onClick={() => setMobileMenuOpen(false)} />
      )}
    </div>
  );
}

function getPageTitle(): string {
  const path = window.location.pathname;
  if (path === '/dashboard') return 'Dashboard';
  if (path.includes('/tenants')) return 'Tenants';
  if (path.includes('/users')) return 'Users';
  if (path.includes('/documents')) return 'Documents';
  return 'Dashboard';
}