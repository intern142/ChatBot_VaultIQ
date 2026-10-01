import { useState, FormEvent, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { login } from '../api/auth';
import { useAuth } from '../context/AuthContext';
import { useLoginLockout } from '../hooks/useLoginLockout';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Alert } from '../components/ui/Alert';

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login: setAuth } = useAuth();
  const from = (location.state as { from?: Location })?.from?.pathname || '/';

  const [form, setForm] = useState({
    organisation_code: '',
    email: '',
    password: '',
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const lockout = useLoginLockout(form.organisation_code, form.email);
  const [locked, setLocked] = useState(false);
  const [countdown, setCountdown] = useState(0);

  useEffect(() => {
    const check = () => setLocked(lockout.isLocked());
    check();
    const id = setInterval(check, 1000);
    return () => clearInterval(id);
  }, [form.organisation_code, form.email, lockout]);

  useEffect(() => {
    if (locked) {
      const id = setInterval(() => setCountdown(lockout.remainingMs()), 1000);
      setCountdown(lockout.remainingMs());
      return () => clearInterval(id);
    }
  }, [locked, lockout]);

  const formatCountdown = (ms: number): string => {
    const totalSeconds = Math.ceil(ms / 1000);
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    if (minutes > 0) return `${minutes}m ${seconds}s`;
    return `${seconds}s`;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (locked) return;
    setError(null);
    setLoading(true);
    try {
      const data = await login(form);
      lockout.recordSuccess();
      setAuth(data.access_token, data.role, data.tenant_id);
      navigate(from, { replace: true });
    } catch (err: any) {
      if (err.status === 401) lockout.recordFailure();
      setError(err.message || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>VaultIQ</h1>
        <p style={styles.subtitle}>Sign in to your organisation</p>
        {error && <Alert variant="error">{error}</Alert>}
        {locked && (
          <Alert variant="warning" style={styles.lockoutAlert}>
            Account locked. Retry in {formatCountdown(countdown)}.
          </Alert>
        )}
        <form onSubmit={handleSubmit} style={styles.form}>
          <div style={styles.field}>
            <label htmlFor="organisation_code" style={styles.label}>
              Organisation Code
            </label>
            <Input
              id="organisation_code"
              name="organisation_code"
              value={form.organisation_code}
              onChange={handleChange}
              placeholder="ACME or SUPER"
              required
              autoComplete="off"
              disabled={locked}
            />
          </div>
          <div style={styles.field}>
            <label htmlFor="email" style={styles.label}>
              Email
            </label>
            <Input
              id="email"
              name="email"
              type="email"
              value={form.email}
              onChange={handleChange}
              placeholder="you@acme.com"
              required
              autoComplete="email"
              disabled={locked}
            />
          </div>
          <div style={styles.field}>
            <label htmlFor="password" style={styles.label}>
              Password
            </label>
            <Input
              id="password"
              name="password"
              type="password"
              value={form.password}
              onChange={handleChange}
              placeholder="••••••••"
              required
              autoComplete="current-password"
              disabled={locked}
            />
          </div>
          <Button type="submit" loading={loading} disabled={locked} style={styles.submit}>
            Sign in
          </Button>
        </form>
        <p style={styles.hint}>
          Use <code>SUPER</code> as organisation code for platform admin.
        </p>
      </div>
    </div>
  );
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
    maxWidth: '400px',
    background: 'white',
    borderRadius: '12px',
    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
    padding: '32px',
  },
  title: {
    margin: '0 0 8px',
    fontSize: '28px',
    fontWeight: 700,
    color: '#0f172a',
  },
  subtitle: {
    margin: '0 0 24px',
    color: '#64748b',
    fontSize: '14px',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
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
  submit: {
    marginTop: '8px',
    height: '44px',
    fontSize: '15px',
    fontWeight: 600,
  },
  hint: {
    marginTop: '20px',
    fontSize: '12px',
    color: '#94a3b8',
    textAlign: 'center',
  },
  lockoutAlert: {
    marginBottom: '16px',
  },
};