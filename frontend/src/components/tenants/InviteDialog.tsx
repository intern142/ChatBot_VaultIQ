import { useState, FormEvent, ChangeEvent } from 'react';
import { inviteTenantAdmin } from '../../api/admin';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Alert } from '../ui/Alert';

interface InviteDialogProps {
  tenantId: string;
  tenantName: string;
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function InviteDialog({ tenantId, tenantName, open, onClose, onSuccess }: InviteDialogProps) {
  if (!open) return null;

  const [form, setForm] = useState({
    email: '',
    expires_in_hours: '168',
  });
  const [code, setCode] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [stage, setStage] = useState<'form' | 'code'>('form');

  const validateEmail = (email: string) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  };

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!validateEmail(form.email)) {
      setError('Please enter a valid email address');
      return;
    }
    const hours = parseInt(form.expires_in_hours, 10);
    if (isNaN(hours) || hours < 1 || hours > 8760) {
      setError('Expiry must be between 1 and 8760 hours');
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const data = await inviteTenantAdmin(tenantId, {
        email: form.email.trim(),
        expires_in_hours: hours,
      });
      setCode(data.code);
      setStage('code');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = async () => {
    if (!code) return;
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSuccess = () => {
    onSuccess();
  };

  if (!open) return null;

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <h3 style={styles.title}>Invite Client Admin</h3>
          <button style={styles.close} onClick={onClose} disabled={loading}>×</button>
        </div>
        {stage === 'form' && (
          <form onSubmit={handleSubmit} style={styles.form}>
            <p style={styles.desc}>Invite the first Client Admin for <strong>{tenantName}</strong>. The invite code will be shown once — copy it immediately.</p>
            {error && <Alert variant="error">{error}</Alert>}
            <div style={styles.field}>
              <label htmlFor="email" style={styles.label}>Email *</label>
              <Input
                id="email"
                name="email"
                type="email"
                value={form.email}
                onChange={handleChange}
                placeholder="admin@acme.com"
                required
                autoComplete="email"
              />
            </div>
            <div style={styles.field}>
              <label htmlFor="expires_in_hours" style={styles.label}>Expires In (hours)</label>
              <Input
                id="expires_in_hours"
                name="expires_in_hours"
                type="number"
                value={form.expires_in_hours}
                onChange={handleChange}
                min="1"
                max="8760"
                placeholder="168 (7 days)"
              />
              <p style={styles.hint}>1–8760 hours. Default 168 (7 days).</p>
            </div>
            <div style={styles.footer}>
              <Button variant="outline" onClick={onClose} disabled={loading}>Cancel</Button>
              <Button type="submit" loading={loading} disabled={loading}>
                Create Invite
              </Button>
            </div>
          </form>
        )}
        {stage === 'code' && code && (
          <div style={styles.codeView}>
            <p style={styles.codeDesc}>Invite created. Copy the code and send it securely to the recipient.</p>
            <div style={styles.codeBox}>
              <code style={styles.codeText}>{code}</code>
              <Button size="sm" onClick={handleCopy} variant={copied ? 'outline' : 'ghost'}>
                {copied ? 'Copied!' : 'Copy'}
              </Button>
            </div>
            <Alert variant="info">
              This code cannot be retrieved again. The invite expires in {form.expires_in_hours} hours.
            </Alert>
            <div style={styles.footer}>
              <Button variant="outline" onClick={() => { setStage('form'); setCode(null); }}>Back</Button>
              <Button onClick={() => { handleSuccess(); onClose(); }}>Done</Button>
            </div>
          </div>
        )}
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
    maxWidth: '520px',
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
  close: { background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer', color: '#64748b', lineHeight: 1, padding: '0 8px' },
  form: { padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' },
  desc: { margin: '0 0 16px', fontSize: '14px', color: '#64748b' },
  field: { display: 'flex', flexDirection: 'column', gap: '6px' },
  label: { fontSize: '13px', fontWeight: 500, color: '#334155' },
  hint: { margin: '4px 0 0', fontSize: '11px', color: '#94a3b8' },
  footer: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '12px',
    padding: '16px 24px',
    borderTop: '1px solid #e2e8f0',
  },
  codeView: {
    padding: '24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  codeDesc: { margin: 0, fontSize: '14px', color: '#64748b' },
  codeBox: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '16px',
    background: '#f1f5f9',
    borderRadius: '8px',
    border: '1px solid #e2e8f0',
  },
  codeText: {
    flex: 1,
    fontSize: '14px',
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
    background: 'white',
    padding: '8px 12px',
    borderRadius: '6px',
    border: '1px solid #e2e8f0',
    wordBreak: 'break-all',
  },
};