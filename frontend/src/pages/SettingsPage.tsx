import { useEffect, useState } from 'react';
import { useTenantSettings } from '@/hooks/useTenantSettings';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Alert } from '@/components/ui/Alert';
import { Spinner } from '@/components/ui/Spinner';
import { EmptyState } from '@/components/ui/EmptyState';
import { SYSTEM_ALLOWED_FORMATS } from '@/config';

type FormatOption = { value: string; label: string };

const FORMAT_OPTIONS: FormatOption[] = SYSTEM_ALLOWED_FORMATS.map((fmt) => ({
  value: fmt,
  label: fmt,
}));

export default function SettingsPage() {
  const { data, loading, saving, uploading, error, success, load, save, uploadLogo, dismissError, dismissSuccess } =
    useTenantSettings();

  const [formData, setFormData] = useState({
    display_name: '',
    accent_colour: '',
    not_found_message: '',
    allowed_upload_formats: '' as string,
  });
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [logoFile, setLogoFile] = useState<File | null>(null);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (data) {
      setFormData({
        display_name: data.display_name ?? '',
        accent_colour: data.accent_colour ?? '',
        not_found_message: data.not_found_message ?? '',
        allowed_upload_formats: data.allowed_upload_formats?.join(',') ?? '',
      });
      setLogoPreview(data.logo_path ?? null);
    }
  }, [data]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const payload = {
      display_name: formData.display_name || null,
      accent_colour: formData.accent_colour || null,
      not_found_message: formData.not_found_message || null,
      allowed_upload_formats: formData.allowed_upload_formats
        ? formData.allowed_upload_formats.split(',').map((s) => s.trim()).filter(Boolean)
        : null,
    };
    await save(payload);
  };

  const handleLogoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith('image/')) {
      alert('Please select an image file.');
      return;
    }
    setLogoFile(file);
    setLogoPreview(URL.createObjectURL(file));
  };

  const handleLogoUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!logoFile) return;
    await uploadLogo(logoFile);
    setLogoFile(null);
  };

  if (loading) {
    return (
      <div style={styles.container}>
        <div style={styles.header}>
          <h1 style={styles.title}>Tenant Settings</h1>
          <Spinner size="md" label="Loading settings…" />
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div style={styles.container}>
        <h1 style={styles.title}>Tenant Settings</h1>
        <EmptyState
          icon="⚙️"
          title="Unable to load settings"
          description={error ?? 'Failed to load tenant settings.'}
          action={{ label: 'Retry', onClick: load }}
        />
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <h1 style={styles.title}>Tenant Settings</h1>

      {error && (
        <Alert variant="error" onDismiss={dismissError} style={styles.alert}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert variant="success" onDismiss={dismissSuccess} style={styles.alert}>
          {success}
        </Alert>
      )}

      <div style={styles.card}>
        <h2 style={styles.sectionTitle}>General</h2>
        <form onSubmit={handleSubmit} style={styles.form}>
          <Input
            name="display_name"
            label="Display Name"
            value={formData.display_name}
            onChange={handleChange}
            placeholder="Optional: custom name for your tenant"
            maxLength={255}
            disabled={saving}
          />

          <Input
            name="accent_colour"
            type="color"
            label="Accent Colour"
            value={formData.accent_colour || '#1e293b'}
            onChange={handleChange}
            disabled={saving}
            style={{ width: '80px', height: '44px', padding: '2px', cursor: 'pointer' }}
          />

          <Input
            name="not_found_message"
            label="Not Found Message"
            value={formData.not_found_message}
            onChange={handleChange}
            placeholder="Plain text only (no HTML/markup), max 500 chars"
            maxLength={500}
            disabled={saving}
            hint="Shown when no answer is found for a question."
          />

          <div style={styles.formGroup}>
            <label style={styles.label}>Allowed Upload Formats</label>
            <Select
              name="allowed_upload_formats"
              multiple
              value={formData.allowed_upload_formats}
              onChange={handleChange}
              options={FORMAT_OPTIONS}
              placeholder="Select allowed formats (empty = all system formats)"
              disabled={saving}
              hint="Hold Ctrl/Cmd to select multiple. Subset of system-allowed formats."
            />
          </div>

          <div style={styles.formGroup}>
            <label style={styles.label}>Conversation Retention (days)</label>
            <Input
              name="conversation_retention_days"
              type="number"
              value={data.conversation_retention_days ?? ''}
              onChange={handleChange}
              min={1}
              max={3650}
              placeholder="Optional: 1–3650 days"
              disabled={saving}
              hint="How long to keep conversation history. Empty = no limit."
            />
          </div>

          <div style={styles.formActions}>
            <Button type="submit" variant="primary" loading={saving} disabled={saving}>
              Save Settings
            </Button>
          </div>
        </form>
      </div>

      <div style={styles.card}>
        <h2 style={styles.sectionTitle}>Logo</h2>
        <form onSubmit={handleLogoUpload} style={styles.form}>
          <div style={styles.logoPreview}>
            {logoPreview ? (
              <img src={logoPreview} alt="Logo preview" style={styles.logoImg} />
            ) : (
              <div style={styles.logoPlaceholder}>No logo uploaded</div>
            )}
          </div>
          <div style={styles.formGroup}>
            <label style={styles.label}>Upload Logo</label>
            <input
              type="file"
              accept="image/*"
              onChange={handleLogoChange}
              style={styles.fileInput}
              disabled={uploading}
            />
            {logoFile && <p style={styles.fileHint}>Selected: {logoFile.name}</p>}
          </div>
          <div style={styles.formActions}>
            <Button type="submit" variant="primary" loading={uploading} disabled={uploading || !logoFile}>
              Upload Logo
            </Button>
          </div>
        </form>
      </div>

      <div style={styles.card}>
        <h2 style={styles.sectionTitle}>Current Values (Read-Only)</h2>
        <div style={styles.readOnlyGrid}>
          <div><strong>Tenant ID:</strong> {data.tenant_id}</div>
          <div><strong>Last Updated By:</strong> {data.updated_by ?? '—'}</div>
          <div><strong>Last Updated At:</strong> {data.updated_at ? new Date(data.updated_at).toLocaleString() : '—'}</div>
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: '24px',
    maxWidth: '800px',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '24px',
  },
  title: {
    margin: 0,
    fontSize: '24px',
    fontWeight: 700,
    color: '#0f172a',
  },
  card: {
    background: 'white',
    border: '1px solid #e2e8f0',
    borderRadius: '12px',
    padding: '24px',
    marginBottom: '24px',
  },
  sectionTitle: {
    margin: '0 0 20px',
    fontSize: '16px',
    fontWeight: 600,
    color: '#1e293b',
    paddingBottom: '12px',
    borderBottom: '1px solid #e2e8f0',
  },
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '20px',
  },
  formGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  label: {
    fontSize: '13px',
    fontWeight: 500,
    color: '#334155',
  },
  formActions: {
    display: 'flex',
    gap: '12px',
    marginTop: '8px',
  },
  alert: {
    marginBottom: '16px',
  },
  logoPreview: {
    width: '120px',
    height: '120px',
    border: '1px solid #e2e8f0',
    borderRadius: '8px',
    overflow: 'hidden',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: '#f8fafc',
    marginBottom: '16px',
  },
  logoImg: {
    width: '100%',
    height: '100%',
    objectFit: 'contain',
  },
  logoPlaceholder: {
    color: '#94a3b8',
    fontSize: '14px',
  },
  fileInput: {
    padding: '8px 12px',
    border: '1px solid #cbd5e1',
    borderRadius: '8px',
    fontSize: '14px',
    cursor: 'pointer',
  },
  fileHint: {
    margin: '8px 0 0',
    fontSize: '13px',
    color: '#64748b',
  },
  readOnlyGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
    gap: '12px',
    fontSize: '14px',
    color: '#475569',
  },
};