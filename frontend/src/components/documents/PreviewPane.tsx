import { useEffect, useState } from 'react';
import { previewDocument, downloadDocument } from '../../api/documents';
import { Alert } from '../ui/Alert';
import { Button } from '../ui/Button';
import { Spinner } from '../ui/Spinner';
import type { PreviewResponse } from '../../api/types';

interface PreviewPaneProps {
  documentId: string;
  filename: string;
  onClose: () => void;
  onError?: (msg: string) => void;
}

export function PreviewPane({ documentId, filename, onClose, onError }: PreviewPaneProps) {
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);
    previewDocument(documentId)
      .then((data) => {
        if (mounted) setPreview(data);
      })
      .catch((err: any) => {
        if (mounted) {
          const msg = err.message || 'Failed to load preview';
          setError(msg);
          onError?.(msg);
        }
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => { /* no cleanup needed */ };
  }, [documentId]);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const blob = await downloadDocument(documentId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(err.message);
    } finally {
      setDownloading(false);
    }
  };

  if (loading) {
    return (
      <div style={styles.overlay} onClick={onClose}>
        <div style={{ ...styles.modal, maxWidth: '500px' }} onClick={(e) => e.stopPropagation()}>
          <div style={styles.loading}>
            <Spinner size="lg" />
            <span>Loading preview…</span>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.overlay} onClick={onClose}>
        <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
          <div style={styles.header}>
            <h3 style={styles.title}>{filename}</h3>
            <button style={styles.close} onClick={onClose}>×</button>
          </div>
          <div style={styles.body}>
            <Alert variant="error">{error}</Alert>
          </div>
          <div style={styles.footer}>
            <Button onClick={onClose}>Close</Button>
          </div>
        </div>
      </div>
    );
  }

  if (!preview) return null;

  const isText = 'truncated' in preview;

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <h3 style={styles.title}>{filename}</h3>
          <button style={styles.close} onClick={onClose}>×</button>
        </div>
        <div style={styles.body}>
          {isText ? (
            <>
              <pre style={styles.previewText}>{preview.preview}</pre>
              {preview.truncated && <p style={styles.truncated}>Preview truncated — download to view full content</p>}
            </>
          ) : (
            <div style={styles.previewOther}>
              <span style={styles.icon}>📄</span>
              <p style={styles.message}>{preview.message}</p>
              <p style={styles.size}>Size: {preview.size_bytes.toLocaleString()} bytes</p>
            </div>
          )}
        </div>
        <div style={styles.footer}>
          <Button variant="outline" onClick={onClose}>Close</Button>
          <Button onClick={handleDownload} loading={downloading}>
            Download
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
    maxWidth: '700px',
    maxHeight: '80vh',
    boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '16px 24px',
    borderBottom: '1px solid #e2e8f0',
  },
  title: { margin: 0, fontSize: '18px', fontWeight: 600, color: '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 'calc(100% - 40px)' },
  close: { background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer', color: '#64748b', lineHeight: 1, padding: '0 8px' },
  body: { padding: '24px', overflow: 'auto', flex: 1 },
  previewText: { margin: 0, fontSize: '14px', lineHeight: '1.6', whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', background: '#f8fafc', padding: '16px', borderRadius: '8px', border: '1px solid #e2e8f0', maxHeight: '50vh', overflow: 'auto' },
  truncated: { margin: '12px 0 0', fontSize: '12px', color: '#94a3b8', fontStyle: 'italic' },
  previewOther: { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '48px', textAlign: 'center', color: '#64748b', gap: '12px' },
  icon: { fontSize: '64px' },
  message: { margin: 0, fontSize: '16px', fontWeight: 500 },
  size: { margin: 0, fontSize: '13px', color: '#94a3b8' },
  footer: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '12px',
    padding: '16px 24px',
    borderTop: '1px solid #e2e8f0',
  },
  loading: { display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '48px', gap: '12px', color: '#64748b' },
};