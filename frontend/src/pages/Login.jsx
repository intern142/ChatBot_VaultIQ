import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { LockoutBanner } from '../components/LockoutBanner';
import { LogoMark, EyeIcon, EyeOffIcon } from '../components/Icons';

export default function Login() {
  const [formData, setFormData] = useState({ orgCode: '', username: '', email: '', password: '', userType: '' });
  const [localError, setLocalError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const { login, isLockedOut, lockoutUntil, error, clearError } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const next = searchParams.get('next') || '/';

  useEffect(() => {
    if (!isLockedOut) clearError();
    setLocalError('');
  }, [isLockedOut, clearError]);

  const handleChange = (e) => {
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const { orgCode, username, email, password, userType } = formData;
    if (!orgCode.trim() || !username.trim() || !email.trim() || !password.trim() || !userType) {
      setLocalError('Invalid credentials');
      return;
    }
    setLocalError('');
    setIsSubmitting(true);
    try {
      const res = await login(formData.orgCode, formData.username, formData.email, formData.password, formData.userType);
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
      <div className="login-split" role="main">
        {/* Left: Branding panel */}
        <div className="login-brand-panel">
          <div className="brand-grid" aria-hidden="true" />
          <div className="brand-shape brand-shape--a" aria-hidden="true" />
          <div className="brand-shape brand-shape--b" aria-hidden="true" />
          <div className="brand-shape brand-shape--c" aria-hidden="true" />
          <div className="brand-content">
            <div className="brand-logo-wrap">
              <span className="brand-logo"><LogoMark /></span>
              <span className="brand-name">VaultIQ</span>
            </div>
            <h1 className="brand-headline">Find the answer.<br />Trust the source.</h1>
            <p className="brand-sub">Your company knowledge, securely at your fingertips.</p>
            <div className="brand-features">
              <span className="brand-feature"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>Encrypted &amp; Secure</span>
              <span className="brand-feature"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><path d="M14 2v6h6"/></svg>Document Management</span>
              <span className="brand-feature"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>AI-Powered Search</span>
            </div>
          </div>
        </div>

        {/* Right: Form panel */}
        <div className="login-form-panel">
          <div className="login-card">
            <div className="login-brand login-brand--form">
              <span className="logo-mark logo-mark--form" aria-hidden="true"><LogoMark /></span>
              <h2 className="login-title">Welcome back</h2>
              <p className="login-subtitle">Sign in to your account</p>
            </div>

            <LockoutBanner lockoutUntil={isLockedOut ? lockoutUntil : 0} onClose={clearError} />

            <form onSubmit={handleSubmit} noValidate>
              <div className="form-group">
                <label htmlFor="username">Username</label>
                <input
                  type="text"
                  id="username"
                  name="username"
                  value={formData.username}
                  onChange={handleChange}
                  placeholder="johndoe"
                  autoComplete="username"
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
                <div className="password-label-row">
                  <label htmlFor="password">Password</label>
                  <a href="/forgot-password" className="forgot-link" tabIndex={-1}>Forgot password?</a>
                </div>
                <div className="password-field-wrap">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    id="password"
                    name="password"
                    value={formData.password}
                    onChange={handleChange}
                    placeholder="••••••••"
                    autoComplete="current-password"
                    disabled={isSubmitting || isLockedOut}
                    required
                  />
                  <button
                    type="button"
                    className="password-toggle"
                    onClick={() => setShowPassword((v) => !v)}
                    tabIndex={-1}
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOffIcon /> : <EyeIcon />}
                  </button>
                </div>
              </div>

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
                <label>User Type</label>
                <div className="role-radio-group" role="radiogroup" aria-label="Select your role">
                  {[
                    { value: 'employee', label: 'Employee' },
                    { value: 'admin', label: 'Admin' },
                    { value: 'super-admin', label: 'Super Admin' },
                  ].map(({ value, label }) => (
                    <label key={value} className="role-radio">
                      <input
                        type="radio"
                        name="userType"
                        value={value}
                        checked={formData.userType === value}
                        onChange={handleChange}
                        disabled={isSubmitting || isLockedOut}
                      />
                      <span>{label}</span>
                    </label>
                  ))}
                </div>
              </div>

              {localError || error ? (
              <div className="form-error" role="alert">
                {localError || error}
              </div>
            ) : null}

              <button type="submit" className="login-btn" disabled={isSubmitting || isLockedOut}>
                {isSubmitting ? (
                  <span className="btn-loading"><span className="spinner" /> Signing in…</span>
                ) : 'Sign In'}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}