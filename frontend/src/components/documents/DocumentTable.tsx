import { useState } from 'react';
import { downloadDocument } from '../../api/documents';
import { PreviewPane } from './PreviewPane';
import { Button } from '../ui/Button';
import { Alert } from '../ui/Alert';
import { Spinner } from '../ui/Spinner';
import { formatBytes, formatDate } from '../../utils/format';
import { DocumentStatusBadge } from './DocumentStatusBadge';
import { DocumentApprovalActions } from './DocumentApprovalActions';
import { ProcessingStatusPanel } from './ProcessingStatusPanel';
import { useDocumentProcessing } from '../../hooks';
import type { DocumentResponse, ProcessingStatusResponse } from '../../api/types';

interface DocumentTableProps {
  documents: DocumentResponse[];
  onDelete: (id: string) => void;
  canDelete: boolean;
  canApprove: boolean;
  canReprocess: boolean;
  loading?: boolean;
}

export function DocumentTable({ documents, onDelete, canDelete, canApprove, canReprocess, loading }: DocumentTableProps) {
  const [previewOpen, setPreviewOpen] = useState<{ id: string; filename: string } | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [statusPanelOpen, setStatusPanelOpen] = useState<string | null>(null);
  const [statusData, setStatusData] = useState<ProcessingStatusResponse | null>(null);

  const { loadStatus, reprocess, loading: processingLoading, error: processingError, clearError: clearProcessingError } = useDocumentProcessing();

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

  const handleOpenStatusPanel = async (id: string) => {
    setStatusPanelOpen(id);
    try {
      const data = await loadStatus(id);
      setStatusData(data);
      clearProcessingError();
    } catch (err) {
      // Error handled by hook
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
              <th style={styles.th}>Status</th>
              <th style={styles.th}>Processing</th>
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
                <td style={styles.td}>
                  <DocumentStatusBadge status={doc.status} processingStatus={doc.processing_status} processingError={doc.processing_error} />
                </td>
                <td style={styles.td}>
                  <DocumentStatusBadge status={doc.status} processingStatus={doc.processing_status} processingError={doc.processing_error} />
                </td>
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
                    <DocumentApprovalActions
                      documentId={doc.id}
                      status={doc.status}
                      isClientAdmin={canApprove}
                      onStatusChange={() => {}}
                    />
                    {canReprocess && doc.processing_status !== 'processing' && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleOpenStatusPanel(doc.id)}
                        disabled={processingLoading}
                      >
                        Processing
                      </Button>
                    )}
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
      {processingError && <Alert variant="error" onDismiss={clearProcessingError}>{processingError}</Alert>}

      {previewOpen && (
        <PreviewPane
          documentId={previewOpen.id}
          filename={previewOpen.filename}
          onClose={() => setPreviewOpen(null)}
        />
      )}

      {statusPanelOpen && (
        <div style={styles.modalOverlay} onClick={() => setStatusPanelOpen(null)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalHeader}>
              <h4>Processing Status</h4>
              <button style={styles.modalClose} onClick={() => setStatusPanelOpen(null)}>×</button>
            </div>
            <div style={styles.modalBody}>
              {processingLoading ? (
                <div style={styles.loading}>Loading processing status…</div>
              ) : (
                <ProcessingStatusPanel
                  status={statusData?.processing_status || 'queued'}
                  error={statusData?.processing_error || null}
                  startedAt={statusData?.processing_started_at || null}
                  completedAt={statusData?.processing_completed_at || null}
                  version={statusData?.processing_version || 1}
                  onReprocess={async () => {
                    await reprocess(statusPanelOpen!);
                    clearProcessingError();
                    // Reload status after reprocess
                    const data = await loadStatus(statusPanelOpen!);
                    setStatusData(data);
                  }}
                  isClientAdmin={canReprocess}
                  loading={processingLoading}
                />
              )}
            </div>
          </div>
        </div>
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
  modalOverlay: {
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
    maxWidth: '600px',
    boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)',
    overflow: 'hidden',
  },
  modalHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '16px 24px',
    borderBottom: '1px solid #e2e8f0',
  },
  modalClose: {
    background: 'none',
    border: 'none',
    fontSize: '24px',
    cursor: 'pointer',
    color: '#64748b',
    lineHeight: 1,
    padding: '0 8px',
  },
  modalBody: { padding: '24px' },
  modalLoading: { display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px', color: '#64748b' },
};