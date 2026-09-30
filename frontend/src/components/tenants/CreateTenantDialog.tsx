import { useState, FormEvent } from 'react';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Alert } from '../ui/Alert';

interface CreateTenantDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: (body: { short_code: string; name: string; storage_quota_mb?: number }) => void;
}

export function CreateTenantDialog({ open, onClose, onSuccess }: CreateTenantDialogProps) {
  if (!open) return null;

  const [form, setForm] = useState({
    short_code: '',
    name: '',
    storage_quota_mb: '',
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const body = {
        short_code: form.short_code.trim(),
        name: form.name.trim(),
        storage_quota_mb: form.storage_quota_mb ? parseInt(form.storage_quota_mb, 10) : undefined,
      };
      await onSuccess(body);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <h3 style={styles.title}>Create Tenant</h3>
          <button style={styles.close} onClick={onClose} disabled={loading}>×</button>
        </div>
        <form onSubmit={handleSubmit} style={styles.form}>
          {error && <Alert variant="error">{error}</Alert>}
          <div style={styles.field}>
            <label htmlFor="short_code" style={styles.label}>Short Code *</label>
            <Input
              id="short_code"
              name="short_code"
              value={form.short_code}
              onChange={(e) => setForm((p) => ({ ...p, short_code: e.target.value.toUpperCase() }))}
              placeholder="ACME"
              maxLength={20}
              required
              pattern="[A-Z0-9]{2,20}"
            />
            <p style={styles.hint}>2-20 uppercase letters/digits. Will be uppercased.</p>
          </div>
          <div style={styles.field}>
            <label htmlFor="name" style={styles.label}>Name *</label>
            <Input
              id="name"
              name="name"
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
              placeholder="Acme Corporation"
              maxLength={255}
              required
            />
          </div>
          <div style={styles.field}>
            <label htmlFor="storage_quota_mb" style={styles.label}>Storage Quota (MB)</label>
            <Input
              id="storage_quota_mb"
              name="storage_quota_mb"
              type="number"
              value={form.storage_quota_mb}
              onChange={(e) => setForm((p) => ({ ...p, storage_quota_mb: e.target.value }))}
              placeholder="Optional (e.g., 2048)"
              min="0"
            />
          </div>
        </form>
        <div style={styles.footer}>
          <Button variant="outline" onClick={onClose} disabled={loading}>Cancel</Button>
          <Button onClick={(e) => { e.preventDefault(); document.querySelector('form')?.dispatchEvent(new Event('submit')); }} loading={loading} disabled={loading}>
            Create
          </Button>
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
  close: { background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer', color: '#64748b', lineHeight: 1, padding: '0 8px' },
  form: { padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' },
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
};