import { useState } from 'react';
import { downloadDocument } from '../../api/documents';
import { PreviewPane } from './PreviewPane';
import { Button } from '../ui/Button';
import { Alert } from '../ui/Alert';
import { Spinner } from '../ui/Spinner';
import { formatBytes, formatDate } from '../../utils/format';

interface DocumentTableProps {
  documents: Array<{
    id: string;
    original_filename: string;
    mime_type: string;
    size_bytes: number;
    created_at: string;
  }>;
  onDelete: (id: string) => void;
  canDelete: boolean;
  loading?: boolean;
}

export function DocumentTable({ documents, onDelete, canDelete, loading }: DocumentTableProps) {
  const [previewOpen, setPreviewOpen] = useState<{ id: string; filename: string } | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const handlePreview = async (id: string, filename: string) => {
    setPreviewOpen({ id, filename });
  };

  const handleDownload = async (id: string, filename: string) => {
    setDownloading(id);
    try {
      const blob = await downloadDocument(id);
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
      setDownloading(null);
    }
  };

  const handleDelete = (id: string) => {
    if (window.confirm('Delete this document? This cannot be undone.')) {
      try {
        onDelete(id);
      } catch (err: any) {
        setDeleteError(err.message);
        setTimeout(() => setDeleteError(null), 5000);
      }
    }
  };

  if (loading) {
    return (
      <div style={styles.loading}>
        <Spinner size="lg" />
        <span>Loading…</span>
      </div>
    );
  }

  return (
    <>
      <div style={styles.tableWrapper}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Name</th>
              <th style={styles.th}>Type</th>
              <th style={styles.th}>Size</th>
              <th style={styles.th}>Uploaded</th>
              <th style={styles.thActions}></th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <tr key={doc.id} style={styles.tr}>
                <td style={styles.td}>
                  <span style={styles.filename}>{doc.original_filename}</span>
                </td>
                <td style={styles.td}>
                  <span style={styles.mime}>{doc.mime_type}</span>
                </td>
                <td style={styles.td}>{formatBytes(doc.size_bytes)}</td>
                <td style={styles.td}>{formatDate(doc.created_at)}</td>
                <td style={styles.tdActions}>
                  <div style={styles.actions}>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handlePreview(doc.id, doc.original_filename)}
                      disabled={previewOpen?.id === doc.id}
                    >
                      Preview
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleDownload(doc.id, doc.original_filename)}
                      loading={downloading === doc.id}
                    >
                      Download
                    </Button>
                    {canDelete && (
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => handleDelete(doc.id)}
                      >
                        Delete
                      </Button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {deleteError && <Alert variant="error" onDismiss={() => setDeleteError(null)}>{deleteError}</Alert>}

      {previewOpen && (
        <PreviewPane
          documentId={previewOpen.id}
          filename={previewOpen.filename}
          onClose={() => setPreviewOpen(null)}
        />
      )}
    </>
  );
}

const styles: Record<string, React.CSSProperties> = {
  tableWrapper: { overflowX: 'auto' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '13px' },
  th: {
    textAlign: 'left',
    padding: '12px 16px',
    borderBottom: '2px solid #e2e8f0',
    fontWeight: 600,
    color: '#334155',
    whiteSpace: 'nowrap',
  },
  thActions: { textAlign: 'right', padding: '12px 16px' },
  tr: { borderBottom: '1px solid #e2e8f0' },
  td: { padding: '12px 16px', color: '#1e293b', whiteSpace: 'nowrap' },
  tdActions: { textAlign: 'right', padding: '12px 16px' },
  filename: { fontWeight: 500, maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', display: 'inline-block' },
  mime: { fontSize: '12px', color: '#64748b', background: '#f1f5f9', padding: '2px 8px', borderRadius: '4px' },
  actions: { display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '8px' },
  loading: { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px', padding: '48px', color: '#64748b' },
};