import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { LockoutBanner } from '../components/LockoutBanner';
import { LogoMark } from '../components/Icons';

export default function Login() {
  const [formData, setFormData] = useState({ orgCode: '', email: '', password: '' });
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login, isLockedOut, lockoutUntil, clearError } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const next = searchParams.get('next') || '/';

  useEffect(() => {
    if (!isLockedOut) clearError();
  }, [isLockedOut, clearError]);

  const handleChange = (e) => {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsSubmitting(true);
    try {
      const res = await login(formData.orgCode, formData.email, formData.password);
      if (res.success) {
        navigate(next, { replace: true });
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
          <p className="login-subtitle">Sign in to your organization</p>
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
              onChange={handleChange}
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
              onChange={handleChange}
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
              onChange={handleChange}
              placeholder="••••••••"
              autoComplete="current-password"
              disabled={isSubmitting || isLockedOut}
              required
            />
          </div>

          {error && <div className="form-error" role="alert">{error}</div>}

          <button type="submit" className="login-btn" disabled={isSubmitting || isLockedOut}>
            {isSubmitting ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
}