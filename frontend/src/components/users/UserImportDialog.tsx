import { useState, ChangeEvent } from 'react';
import { Button } from '../ui/Button';
import { Alert } from '../ui/Alert';
import { Spinner } from '../ui/Spinner';
import type { ImportResponse, ImportRowResult } from '../../api/types';

interface UserImportDialogProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (file: File) => Promise<ImportResponse | null>;
}

interface ImportRowDisplay extends ImportRowResult {
  expanded?: boolean;
}

export function UserImportDialog({ open, onClose, onSubmit }: UserImportDialogProps) {
  if (!open) return null;

  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ImportResponse | null>(null);
  const [rows, setRows] = useState<ImportRowDisplay[]>([]);

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) {
      if (!f.name.endsWith('.csv')) {
        setError('File must be a CSV file');
        setFile(null);
      } else {
        setError(null);
        setFile(f);
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);
    setRows([]);

    try {
      const result = await onSubmit(file);
      if (result) {
        setResult(result);
        setRows(result.rows);
      }
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setFile(null);
    setError(null);
    setLoading(false);
    setResult(null);
    setRows([]);
    onClose();
  };

  if (!open) return null;

  return (
    <div style={styles.overlay} onClick={handleClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <h3 style={styles.title}>Import Users from CSV</h3>
          <button style={styles.close} onClick={handleClose} disabled={loading}>
            ×
          </button>
        </div>
        <div style={styles.body}>
          {error && <Alert variant="error">{error}</Alert>}

          {result && (
            <div style={styles.resultCard}>
              <h4 style={styles.resultTitle}>
                {result.applied ? 'Import Successful' : 'Import Failed'}
              </h4>
              <p style={styles.resultMessage}>{result.message}</p>
              <div style={styles.resultStats}>
                <div style={styles.stat}>
                  <span style={styles.statValue}>{result.total_rows}</span>
                  <span style={styles.statLabel}>Total Rows</span>
                </div>
                <div style={styles.stat}>
                  <span style={styles.statValue}>{result.created_count}</span>
                  <span style={styles.statLabel}>Created</span>
                </div>
                <div style={styles.stat}>
                  <span style={styles.statValue}>{result.invalid_count}</span>
                  <span style={styles.statLabel}>Invalid</span>
                </div>
              </div>

              {rows.length > 0 && (
                <div style={styles.rowsContainer}>
                  <h5 style={styles.rowsTitle}>Row Details</h5>
                  <div style={styles.rowsTable}>
                    <div style={styles.rowHeader}>
                      <span style={styles.rowCell}>Line</span>
                      <span style={styles.rowCell}>Email</span>
                      <span style={styles.rowCell}>Status</span>
                      <span style={styles.rowCell}>Reason</span>
                    </div>
                    {rows.map((row) => (
                      <div key={row.line} style={styles.row}>
                        <span style={styles.rowCell}>{row.line}</span>
                        <span style={styles.rowCell}>{row.email}</span>
                        <span style={styles.rowCell}>
                          <span
                            style={{
                              ...styles.statusBadge,
                              backgroundColor:
                                row.status === 'created'
                                  ? '#dcfce7'
                                  : row.status === 'not_created'
                                  ? '#fef3c7'
                                  : '#fee2e2',
                              color:
                                row.status === 'created'
                                  ? '#16a34a'
                                  : row.status === 'not_created'
                                  ? '#f59e0b'
                                  : '#dc2626',
                            }}
                          >
                            {row.status}
                          </span>
                        </span>
                        <span style={styles.rowCell}>{row.reason || '—'}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div style={styles.footer}>
                <Button onClick={handleClose}>Close</Button>
              </div>
            </div>
          )}

          {!result && (
            <form onSubmit={handleSubmit}>
              <div style={styles.dropzone}>
                <input
                  type="file"
                  id="csv-file"
                  accept=".csv"
                  onChange={handleFileChange}
                  disabled={loading}
                  style={styles.input}
                />
                <label htmlFor="csv-file" style={styles.label}>
                  {file ? (
                    <div style={styles.selectedFile}>
                      <span style={styles.fileIcon}>📄</span>
                      <div style={styles.fileInfo}>
                        <span style={styles.fileName}>{file.name}</span>
                        <span style={styles.fileSize}>
                          {(file.size / 1024).toFixed(1)} KB
                        </span>
                      </div>
                    </div>
                  ) : (
                    <>
                      <span style={styles.icon}>📎</span>
                      <p style={styles.text}>Click or drag a CSV file here</p>
                      <p style={styles.hint}>
                        Format: email,role (one per line)<br />
                        Max 500 rows, 1 MB
                      </p>
                    </>
                  )}
                </label>
              </div>

              <div style={styles.templateSection}>
                <p style={styles.templateTitle}>CSV Template</p>
                <pre style={styles.templateCode}>email,role
user1@example.com,employee
user2@example.com,client_admin
user3@example.com,employee</pre>
                <p style={styles.templateNote}>
                  Roles: <code>employee</code> or <code>client_admin</code>
                </p>
              </div>

              <div style={styles.footer}>
                <Button variant="outline" onClick={handleClose} disabled={loading}>
                  Cancel
                </Button>
                <Button type="submit" loading={loading} disabled={!file || loading}>
                  {loading ? <><Spinner size="sm" /> Importing…</> : 'Import Users'}
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
    maxWidth: '720px',
    maxHeight: '90vh',
    boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
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
  body: { padding: '24px', overflow: 'auto', flex: 1 },
  dropzone: {
    border: '2px dashed #cbd5e1',
    borderRadius: '8px',
    padding: '32px',
    textAlign: 'center',
    marginBottom: '24px',
  },
  label: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '12px', cursor: 'pointer' },
  input: { display: 'none' },
  icon: { fontSize: '48px' },
  text: { margin: 0, fontSize: '16px', fontWeight: 500, color: '#334155' },
  hint: { margin: '8px 0 0', fontSize: '12px', color: '#94a3b8', whiteSpace: 'pre-line' },
  selectedFile: { display: 'flex', alignItems: 'center', gap: '12px', padding: '12px', background: '#f1f5f9', borderRadius: '8px' },
  fileIcon: { fontSize: '24px' },
  fileInfo: { display: 'flex', flexDirection: 'column' },
  fileName: { fontWeight: 500, fontSize: '14px' },
  fileSize: { fontSize: '12px', color: '#64748b' },
  templateSection: {
    marginTop: '16px',
    padding: '16px',
    background: '#f8fafc',
    borderRadius: '8px',
    border: '1px solid #e2e8f0',
  },
  templateTitle: { margin: '0 0 8px', fontSize: '14px', fontWeight: 600, color: '#334155' },
  templateCode: {
    margin: '0 0 8px',
    padding: '12px',
    background: '#1e293b',
    color: '#e2e8f0',
    borderRadius: '6px',
    fontSize: '13px',
    fontFamily: 'monospace',
    overflow: 'auto',
  },
  templateNote: { margin: 0, fontSize: '12px', color: '#64748b' },
  resultCard: {
    padding: '24px',
    background: '#f8fafc',
    border: '1px solid #e2e8f0',
    borderRadius: '8px',
    marginBottom: '16px',
  },
  resultTitle: { margin: '0 0 8px', fontSize: '16px', fontWeight: 600 },
  resultMessage: { margin: '0 0 16px', color: '#64748b' },
  resultStats: {
    display: 'flex',
    gap: '24px',
    marginBottom: '16px',
    padding: '16px',
    background: 'white',
    borderRadius: '8px',
    border: '1px solid #e2e8f0',
  },
  stat: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' },
  statValue: { fontSize: '24px', fontWeight: 700, color: '#0f172a' },
  statLabel: { fontSize: '12px', color: '#64748b' },
  rowsContainer: { marginTop: '16px' },
  rowsTitle: { margin: '0 0 12px', fontSize: '14px', fontWeight: 600 },
  rowsTable: { border: '1px solid #e2e8f0', borderRadius: '8px', overflow: 'hidden' },
  rowHeader: {
    display: 'grid',
    gridTemplateColumns: '60px 1fr 100px 1fr',
    padding: '8px 12px',
    background: '#f8fafc',
    borderBottom: '1px solid #e2e8f0',
    fontSize: '12px',
    fontWeight: 600,
    color: '#64748b',
  },
  row: {
    display: 'grid',
    gridTemplateColumns: '60px 1fr 100px 1fr',
    padding: '8px 12px',
    borderBottom: '1px solid #e2e8f0',
    fontSize: '13px',
    alignItems: 'center',
  },
  rowCell: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
  statusBadge: { fontSize: '11px', fontWeight: 600, padding: '2px 8px', borderRadius: '4px', textTransform: 'capitalize' },
  footer: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '12px',
    paddingTop: '16px',
    borderTop: '1px solid #e2e8f0',
    marginTop: '16px',
  },
};