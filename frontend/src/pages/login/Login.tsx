import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import api from '../../api/auth';
import { LockIcon, UserIcon, EmailIcon, BuildingIcon, LoaderIcon } from '../../components/Icons';
import type { LoginRequest } from '../../api/types';

export function Login() {
  const { login, error } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState<LoginRequest>({
    orgCode: 'ORG-12345',
    username: '',
    email: '',
    password: '',
    role: 'employee',
  });
  const [loading, setLoading] = useState(false);

  const from = (location.state as { from?: Location })?.from?.pathname || '/dashboard';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await login(form);
      navigate(from, { replace: true });
    } catch {
      // Error handled by context
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-brand">
        <div className="login-brand-logo">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" width="48" height="48">
            <rect x="3" y="3" width="18" height="18" rx="3" />
            <path d="M8 16l4-8 4 8" />
            <path d="M10 13h4" />
          </svg>
        </div>
        <h1>VaultIQ</h1>
        <p>Secure Multi-Tenant Collaboration Platform</p>
      </div>
      <div className="login-form-container">
        <form onSubmit={handleSubmit} className="login-form">
          <h2>Sign in to your account</h2>
          {error && <div className="alert alert-error">{error}</div>}
          <div className="form-group">
            <label htmlFor="orgCode">Organization Code</label>
            <div className="input-with-icon">
              <BuildingIcon />
              <select
                id="orgCode"
                value={form.orgCode}
                onChange={e => setForm(f => ({ ...f, orgCode: e.target.value }))}
                required
              >
                <option value="ORG-12345">Acme Corp (ORG-12345)</option>
                <option value="ORG-67890">Beta Labs (ORG-67890)</option>
              </select>
            </div>
          </div>
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <div className="input-with-icon">
              <UserIcon />
              <input
                id="username"
                type="text"
                value={form.username}
                onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                placeholder="Enter username"
                required
              />
            </div>
          </div>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <div className="input-with-icon">
              <EmailIcon />
              <input
                id="email"
                type="email"
                value={form.email}
                onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                placeholder="Enter email"
                required
              />
            </div>
          </div>
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <div className="input-with-icon">
              <LockIcon />
              <input
                id="password"
                type="password"
                value={form.password}
                onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                placeholder="Enter password"
                required
              />
            </div>
          </div>
          <div className="form-group">
            <label htmlFor="role">Role</label>
            <div className="input-with-icon">
              <ShieldIcon />
              <select
                id="role"
                value={form.role}
                onChange={e => setForm(f => ({ ...f, role: e.target.value as LoginRequest['role'] }))}
                required
              >
                <option value="employee">Employee</option>
                <option value="client_admin">Client Admin</option>
                <option value="super_admin">Super Admin</option>
              </select>
            </div>
          </div>
          <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
            {loading ? <><LoaderIcon className="spin" /> Signing in...</> : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
}