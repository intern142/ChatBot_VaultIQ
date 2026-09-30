import { useState, ChangeEvent } from 'react';
import { uploadDocument } from '../../api/documents';
import { Button } from '../ui/Button';
import { Alert } from '../ui/Alert';
import { ALLOWED_MIME_TYPES, MAX_FILE_SIZE_MB } from '../../config';

interface UploadDialogProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

const ALLOWED_EXTENSIONS = ['.pdf', '.txt', '.md', '.doc', '.docx', '.xls', '.xlsx', '.csv'];

export function UploadDialog({ open, onClose, onSuccess }: UploadDialogProps) {
  if (!open) return null;

  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const validateFile = (f: File): string | null => {
    if (f.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      return `File too large. Maximum size is ${MAX_FILE_SIZE_MB}MB.`;
    }
    if (!ALLOWED_MIME_TYPES.includes(f.type as any)) {
      return `Unsupported file type. Allowed: ${ALLOWED_MIME_TYPES.join(', ')}`;
    }
    const ext = '.' + f.name.split('.').pop()?.toLowerCase();
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `Unsupported file extension. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}`;
    }
    return null;
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) {
      const err = validateFile(f);
      if (err) {
        setError(err);
        setFile(null);
      } else {
        setError(null);
        setFile(f);
      }
    }
  };

  const handleSubmit = async () => {
    if (!file || loading) return;
    setLoading(true);
    setError(null);
    try {
      await uploadDocument(file);
      onSuccess();
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
          <h3 style={styles.title}>Upload Document</h3>
          <button style={styles.close} onClick={onClose} disabled={loading}>
            ×
          </button>
        </div>
        <div style={styles.body}>
          {error && <Alert variant="error">{error}</Alert>}
          <div style={styles.dropzone}>
            <input
              type="file"
              id="file-upload"
              accept={ALLOWED_MIME_TYPES.join(',')}
              onChange={handleFileChange}
              disabled={loading}
              style={styles.input}
            />
            <label htmlFor="file-upload" style={styles.label}>
              {file ? (
                <div style={styles.selectedFile}>
                  <span style={styles.fileName}>{file.name}</span>
                  <span style={styles.fileSize}>{(file.size / 1024 / 1024).toFixed(2)} MB</span>
                </div>
              ) : (
                <>
                  <span style={styles.icon}>📎</span>
                  <p style={styles.text}>Click or drag a file here</p>
                  <p style={styles.hint}>
                    Allowed: {ALLOWED_EXTENSIONS.join(', ')} • Max {MAX_FILE_SIZE_MB}MB
                  </p>
                </>
              )}
            </label>
          </div>
        </div>
        <div style={styles.footer}>
          <Button variant="outline" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} loading={loading} disabled={!file || loading}>
            {loading ? 'Uploading…' : 'Upload'}
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
  dropzone: {
    border: '2px dashed #cbd5e1',
    borderRadius: '8px',
    padding: '32px',
    textAlign: 'center',
    transition: 'border-color 0.15s, background 0.15s',
  },
  label: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', cursor: 'pointer' },
  input: { display: 'none' },
  icon: { fontSize: '48px' },
  text: { margin: 0, fontSize: '16px', fontWeight: 500, color: '#334155' },
  hint: { margin: '8px 0 0', fontSize: '12px', color: '#94a3b8' },
  selectedFile: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', maxWidth: '300px', padding: '12px', background: '#f1f5f9', borderRadius: '8px' },
  fileName: { fontWeight: 500, fontSize: '14px' },
  fileSize: { fontSize: '13px', color: '#64748b' },
  footer: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '12px',
    padding: '16px 24px',
    borderTop: '1px solid #e2e8f0',
  },
};