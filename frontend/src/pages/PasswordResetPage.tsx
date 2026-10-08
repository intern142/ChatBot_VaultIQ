import { useState, FormEvent } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { resetPassword } from '../api/auth';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Alert } from '../components/ui/Alert';
import { Spinner } from '../components/ui/Spinner';

const SPECIAL_CHARS = '! @ # $ % ^ & * ( ) _ + - = [ ] { } ; \' : " | , . < > / ?';

export default function PasswordResetPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({
    code: '',
    new_password: '',
    confirm_password: '',
  });
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  // Get code from URL query params
  const searchParams = new URLSearchParams(location.search);
  const urlCode = searchParams.get('code');
  if (urlCode) {
    setForm((prev) => ({ ...prev, code: urlCode }));
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!form.code.trim()) {
      setError('Reset code is required');
      return;
    }

    if (!form.new_password) {
      setError('New password is required');
      return;
    }

    if (form.new_password !== form.confirm_password) {
      setError('Passwords do not match');
      return;
    }

    // Password strength validation (client-side)
    const errors = validatePasswordStrength(form.new_password);
    if (errors.length > 0) {
      setError(errors.join('; '));
      return;
    }

    setLoading(true);
    try {
      await resetPassword({
        code: form.code.trim(),
        new_password: form.new_password,
      });
      setSuccess(true);
      setForm({ code: '', new_password: '', confirm_password: '' });
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  if (success) {
    return (
      <div style={styles.container}>
        <div style={styles.card}>
          <div style={styles.successIcon}>✅</div>
          <h1 style={styles.title}>Password Updated</h1>
          <p style={styles.message}>
            Your password has been successfully updated. All existing sessions have been signed out.
          </p>
          <Button onClick={() => navigate('/login')} style={{ ...styles.button, width: '100%' }}>
            Go to Login
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <div style={styles.logo}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" width="48" height="48">
            <rect x="3" y="3" width="18" height="18" rx="3" />
            <path d="M8 16l4-8 4 8" />
            <path d="M10 13h4" />
          </svg>
        </div>
        <h1 style={styles.title}>Reset Password</h1>
        <p style={styles.subtitle}>Enter your reset code and new password</p>

        {error && <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>}

        <form onSubmit={handleSubmit} style={styles.form}>
          <div style={styles.field}>
            <label htmlFor="code" style={styles.label}>
              Reset Code
            </label>
            <Input
              id="code"
              name="code"
              type="text"
              value={form.code}
              onChange={handleChange}
              placeholder="Enter reset code"
              required
              autoComplete="off"
              disabled={loading}
            />
          </div>

          <div style={styles.field}>
            <label htmlFor="new_password" style={styles.label}>
              New Password
            </label>
            <Input
              id="new_password"
              name="new_password"
              type="password"
              value={form.new_password}
              onChange={handleChange}
              placeholder="Enter new password"
              required
              autoComplete="new-password"
              disabled={loading}
            />
          </div>

          <div style={styles.field}>
            <label htmlFor="confirm_password" style={styles.label}>
              Confirm Password
            </label>
            <Input
              id="confirm_password"
              name="confirm_password"
              type="password"
              value={form.confirm_password}
              onChange={handleChange}
              placeholder="Confirm new password"
              required
              autoComplete="new-password"
              disabled={loading}
            />
          </div>

          <div style={styles.requirements}>
            <p style={styles.reqTitle}>Password must contain:</p>
            <ul style={styles.reqList}>
              <li>At least 8 characters</li>
              <li>One uppercase letter</li>
              <li>One lowercase letter</li>
              <li>One digit</li>
              <li>One special character</li>
            </ul>
            <p style={styles.reqNote}>Special characters: {SPECIAL_CHARS}</p>
          </div>

          <Button type="submit" loading={loading} style={{ ...styles.submit, width: '100%' }}>
            {loading ? <><Spinner size="sm" /> Resetting…</> : 'Reset Password'}
          </Button>
        </form>

        <p style={styles.backLink}>
          <a href="/login" onClick={(e) => { e.preventDefault(); navigate('/login'); }}>
            Back to login
          </a>
        </p>
      </div>
    </div>
  );
}

function validatePasswordStrength(password: string): string[] {
  const errors: string[] = [];
  if (password.length < 8) errors.push('at least 8 characters');
  if (!/[A-Z]/.test(password)) errors.push('one uppercase letter');
  if (!/[a-z]/.test(password)) errors.push('one lowercase letter');
  if (!/[0-9]/.test(password)) errors.push('one digit');
  if (!/[!@#$%^&*()_+\-=[\]{};':"|,.<>/?]/.test(password)) errors.push('one special character');
  return errors;
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '24px',
    background: '#f8fafc',
  },
  card: {
    width: '100%',
    maxWidth: '440px',
    background: 'white',
    borderRadius: '12px',
    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
    padding: '40px',
  },
  logo: {
    display: 'flex',
    justifyContent: 'center',
    marginBottom: '24px',
    color: '#0f172a',
  },
  title: {
    margin: '0 0 8px',
    fontSize: '24px',
    fontWeight: 700,
    color: '#0f172a',
    textAlign: 'center',
  },
  subtitle: {
    margin: '0 0 24px',
    color: '#64748b',
    textAlign: 'center',
    fontSize: '14px',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
  field: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  label: {
    fontSize: '13px',
    fontWeight: 500,
    color: '#334155',
  },
  requirements: {
    marginTop: '8px',
    padding: '16px',
    background: '#f8fafc',
    borderRadius: '8px',
    border: '1px solid #e2e8f0',
  },
  reqTitle: { margin: '0 0 8px', fontSize: '12px', fontWeight: 600, color: '#334155' },
  reqList: { margin: 0, paddingLeft: '20px', fontSize: '12px', color: '#64748b', lineHeight: '1.8' },
  reqNote: { margin: '8px 0 0', fontSize: '11px', color: '#94a3b8' },
  submit: {
    marginTop: '8px',
    height: '44px',
    fontSize: '15px',
    fontWeight: 600,
  },
  backLink: {
    marginTop: '24px',
    textAlign: 'center',
    fontSize: '13px',
    color: '#64748b',
  },
  successIcon: {
    display: 'flex',
    justifyContent: 'center',
    marginBottom: '16px',
    fontSize: '48px',
  },
  message: {
    margin: '0 0 24px',
    textAlign: 'center',
    color: '#64748b',
    lineHeight: '1.6',
  },
  button: { height: '44px', fontSize: '15px', fontWeight: 600 },
};