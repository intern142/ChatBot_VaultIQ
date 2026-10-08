import { useState } from 'react';
import { Button } from '../ui/Button';
import { Alert } from '../ui/Alert';
import { Spinner } from '../ui/Spinner';
import type { UserInviteCreate, UserInviteIssued } from '../../api/types';

interface UserInviteDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: UserInviteCreate) => Promise<UserInviteIssued | null>;
}

const ROLE_OPTIONS = [
  { value: 'employee', label: 'Employee' },
  { value: 'client_admin', label: 'Client Admin' },
] as const;

export function UserInviteDialog({ open, onClose, onSubmit }: UserInviteDialogProps) {
  if (!open) return null;

  const [email, setEmail] = useState('');
  const [role, setRole] = useState<'employee' | 'client_admin'>('employee');
  const [expiresInHours, setExpiresInHours] = useState(168);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [successData, setSuccessData] = useState<UserInviteIssued | null>(null);

  const validateEmail = (value: string): string | null => {
    if (!value) return 'Email is required';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) return 'Invalid email format';
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const emailError = validateEmail(email);
    if (emailError) {
      setError(emailError);
      return;
    }

    setLoading(true);
    try {
      const result = await onSubmit({
        email: email.trim().toLowerCase(),
        role,
        expires_in_hours: expiresInHours,
      });
      if (result) {
        setSuccessData(result);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setEmail('');
    setRole('employee');
    setExpiresInHours(168);
    setError(null);
    setSuccessData(null);
    onClose();
  };

  if (!open) return null;

  return (
    <div style={styles.overlay} onClick={handleClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <h3 style={styles.title}>Invite User</h3>
          <button style={styles.close} onClick={handleClose} disabled={loading}>
            ×
          </button>
        </div>
        <div style={styles.body}>
          {error && <Alert variant="error">{error}</Alert>}

          {successData && (
            <div style={styles.successCard}>
              <h4 style={styles.successTitle}>Invitation Created</h4>
              <p style={styles.successText}>Share this code with the user. It cannot be retrieved again.</p>
              <div style={styles.codeContainer}>
                <code style={styles.code}>{successData.code}</code>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    navigator.clipboard.writeText(successData.code);
                    alert('Code copied to clipboard');
                  }}
                >
                  Copy
                </Button>
              </div>
              <p style={styles.successDetails}>
                <strong>Email:</strong> {successData.email}<br />
                <strong>Role:</strong> {successData.role}<br />
                <strong>Expires:</strong> {new Date(successData.expires_at).toLocaleString()}
              </p>
              <Button onClick={handleClose} style={styles.doneButton}>
                Done
              </Button>
            </div>
          )}

          {!successData && (
            <form onSubmit={handleSubmit}>
              <div style={styles.formGroup}>
                <label htmlFor="invite-email" style={styles.label}>
                  Email
                </label>
                <input
                  id="invite-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="user@example.com"
                  required
                  disabled={loading}
                  autoComplete="email"
                  style={styles.input}
                />
              </div>
              <div style={styles.formGroup}>
                <label htmlFor="invite-role" style={styles.label}>
                  Role
                </label>
                <select
                  id="invite-role"
                  value={role}
                  onChange={(e) => setRole(e.target.value as 'employee' | 'client_admin')}
                  style={styles.select}
                  disabled={loading}
                  required
                >
                  {ROLE_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              <div style={styles.formGroup}>
                <label htmlFor="invite-expires" style={styles.label}>
                  Expires In (hours)
                </label>
                <input
                  id="invite-expires"
                  type="number"
                  value={expiresInHours}
                  onChange={(e) => setExpiresInHours(Math.max(1, parseInt(e.target.value) || 1))}
                  style={styles.input}
                  min={1}
                  max={8760}
                  required
                  disabled={loading}
                />
              </div>
              <div style={styles.footer}>
                <Button variant="outline" onClick={handleClose} disabled={loading}>
                  Cancel
                </Button>
                <Button type="submit" loading={loading} disabled={loading}>
                  {loading ? <><Spinner size="sm" /> Inviting…</> : 'Send Invitation'}
                </Button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  overlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.5)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '24px',
    zIndex: 100,
  },
  modal: {
    background: 'white',
    borderRadius: '12px',
    width: '100%',
    maxWidth: '480px',
    boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '16px 24px',
    borderBottom: '1px solid #e2e8f0',
  },
  title: { margin: 0, fontSize: '18px', fontWeight: 600, color: '#0f172a' },
  close: {
    background: 'none',
    border: 'none',
    fontSize: '24px',
    cursor: 'pointer',
    color: '#64748b',
    lineHeight: 1,
    padding: '0 8px',
  },
  body: { padding: '24px' },
  formGroup: { marginBottom: '16px' },
  label: { display: 'block', marginBottom: '6px', fontSize: '13px', fontWeight: 500, color: '#334155' },
  select: { width: '100%', padding: '8px 12px', border: '1px solid #cbd5e1', borderRadius: '6px', fontSize: '14px' },
  input: { width: '100%', padding: '8px 12px', border: '1px solid #cbd5e1', borderRadius: '6px', fontSize: '14px' },
  footer: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '12px',
    paddingTop: '16px',
    borderTop: '1px solid #e2e8f0',
    marginTop: '8px',
  },
  successCard: {
    padding: '16px',
    background: '#f0fdf4',
    border: '1px solid #bbf7d0',
    borderRadius: '8px',
    marginBottom: '16px',
  },
  successTitle: { margin: '0 0 8px', fontSize: '16px', fontWeight: 600, color: '#166534' },
  successText: { margin: '0 0 12px', fontSize: '14px', color: '#166534' },
  codeContainer: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    marginBottom: '16px',
    padding: '12px',
    background: 'white',
    border: '1px solid #d1fae5',
    borderRadius: '6px',
  },
  code: { fontSize: '16px', fontFamily: 'monospace', background: '#f0fdf4', padding: '8px 12px', borderRadius: '4px', flex: 1 },
  successDetails: { margin: 0, fontSize: '13px', color: '#166534', lineHeight: 1.8 },
  doneButton: { width: '100%' },
};