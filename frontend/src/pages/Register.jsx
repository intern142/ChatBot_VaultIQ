import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { LockoutBanner } from '../components/LockoutBanner';
import { LogoMark } from '../components/Icons';

const ROLE_OPTIONS = [
  { value: 'employee', label: 'Employee' },
  { value: 'client-admin', label: 'Client Admin' },
  { value: 'super-admin', label: 'Super Admin' },
];

export default function Register() {
  const [formData, setFormData] = useState({ orgCode: '', email: '', password: '', role: 'employee' });
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { register, isLockedOut, lockoutUntil, clearError } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isLockedOut) clearError();
  }, [isLockedOut, clearError]);

  const handleChange = (e) => {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!formData.orgCode.trim() || !formData.email.trim() || !formData.password) {
      setError('All fields are required');
      return;
    }
    setIsSubmitting(true);
    try {
      const res = await register(formData.orgCode, formData.email, formData.password, formData.role);
      if (res.success) {
        navigate('/', { replace: true });
      }
    } catch {
      // error handled by AuthContext
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="login-page">
      <div className="login-card" role="main">
        <div className="login-brand">
          <span className="logo-mark" aria-hidden="true"><LogoMark /></span>
          <h1 className="login-title">VaultIQ</h1>
          <p className="login-subtitle">Create your account</p>
        </div>

        <LockoutBanner lockoutUntil={isLockedOut ? lockoutUntil : 0} onClose={clearError} />

        <form onSubmit={handleSubmit} noValidate>
          <div className="form-group">
            <label htmlFor="orgCode">Organization Code</label>
            <input
              type="text"
              id="orgCode"
              name="orgCode"
              value={formData.orgCode}
              onChange={(e) => setFormData((p) => ({ ...p, orgCode: e.target.value }))}
              placeholder="ORG-12345"
              autoComplete="organization"
              disabled={isSubmitting || isLockedOut}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={(e) => setFormData((p) => ({ ...p, email: e.target.value }))}
              placeholder="you@company.com"
              autoComplete="email"
              disabled={isSubmitting || isLockedOut}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              type="password"
              id="password"
              name="password"
              value={formData.password}
              onChange={(e) => setFormData((p) => ({ ...p, password: e.target.value }))}
              placeholder="Min. 8 characters"
              autoComplete="new-password"
              disabled={isSubmitting || isLockedOut}
              required
              minLength={8}
            />
          </div>

          <div className="form-group">
            <label htmlFor="role">Role</label>
            <select
              id="role"
              name="role"
              value={formData.role}
              onChange={(e) => setFormData((p) => ({ ...p, role: e.target.value }))}
              disabled={isSubmitting || isLockedOut}
            >
              {ROLE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>

          {error && <div className="form-error" role="alert">{error}</div>}

          <button type="submit" className="login-btn" disabled={isSubmitting || isLockedOut}>
            {isSubmitting ? 'Creating account…' : 'Create Account'}
          </button>
        </form>

        <div className="auth-switch">
          Already have an account? <Link to="/login">Sign in</Link>
        </div>
      </div>
    </div>
  );
}