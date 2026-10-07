import { useState } from 'react';
import { Button } from '../ui/Button';
import { Alert } from '../ui/Alert';
import { approveDocument, rejectDocument, getVersionHistory } from '../../api/documents';
import type { VersionHistoryResponse } from '../../api/types';

interface DocumentApprovalActionsProps {
  documentId: string;
  status: string;
  isClientAdmin: boolean;
  onStatusChange: () => void;
}

export function DocumentApprovalActions({ documentId, status, isClientAdmin, onStatusChange }: DocumentApprovalActionsProps) {
  const [showRejectNote, setShowRejectNote] = useState(false);
  const [showApproveNote, setShowApproveNote] = useState(false);
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showVersionHistory, setShowVersionHistory] = useState(false);
  const [versions, setVersions] = useState<VersionHistoryResponse | null>(null);
  const [versionsLoading, setVersionsLoading] = useState(false);

  const handleApprove = async () => {
    setError(null);
    setLoading(true);
    try {
      await approveDocument(documentId, { note: note || undefined });
      setShowApproveNote(false);
      setNote('');
      onStatusChange();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    setError(null);
    setLoading(true);
    try {
      await rejectDocument(documentId, { note: note || undefined });
      setShowRejectNote(false);
      setNote('');
      onStatusChange();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLoadVersions = async () => {
    setVersionsLoading(true);
    try {
      const data = await getVersionHistory(documentId);
      setVersions(data);
      setShowVersionHistory(true);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setVersionsLoading(false);
    }
  };

  if (!isClientAdmin) return null;

  return (
    <div style={styles.container}>
      {status === 'pending' && (
        <div style={styles.actionGroup}>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowApproveNote(true)}
            disabled={loading}
          >
            Approve
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowRejectNote(true)}
            disabled={loading}
          >
            Reject
          </Button>
        </div>
      )}

      {status === 'approved' && (
        <Button variant="ghost" size="sm" onClick={handleLoadVersions} disabled={versionsLoading}>
          Version History
        </Button>
      )}

      {showApproveNote && (
        <div style={styles.modalOverlay} onClick={() => setShowApproveNote(false)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalHeader}>
              <h4>Approve Document</h4>
              <button style={styles.modalClose} onClick={() => setShowApproveNote(false)}>×</button>
            </div>
            <div style={styles.modalBody}>
              <textarea
                style={styles.textarea}
                placeholder="Optional approval note..."
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={3}
              />
              {error && <Alert variant="error">{error}</Alert>}
              <div style={styles.modalFooter}>
                <Button variant="outline" onClick={() => setShowApproveNote(false)}>Cancel</Button>
                <Button onClick={handleApprove} loading={loading}>Approve</Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showRejectNote && (
        <div style={styles.modalOverlay} onClick={() => setShowRejectNote(false)}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalHeader}>
              <h4>Reject Document</h4>
              <button style={styles.modalClose} onClick={() => setShowRejectNote(false)}>×</button>
            </div>
            <div style={styles.modalBody}>
              <textarea
                style={styles.textarea}
                placeholder="Rejection reason (optional)..."
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={3}
              />
              {error && <Alert variant="error">{error}</Alert>}
              <div style={styles.modalFooter}>
                <Button variant="outline" onClick={() => setShowRejectNote(false)}>Cancel</Button>
                <Button variant="danger" onClick={handleReject} loading={loading}>Reject</Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showVersionHistory && versions && (
        <div style={styles.modalOverlay} onClick={() => setShowVersionHistory(false)}>
          <div style={styles.modalWide} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalHeader}>
              <h4>Version History</h4>
              <button style={styles.modalClose} onClick={() => setShowVersionHistory(false)}>×</button>
            </div>
            <div style={styles.modalBody}>
              {versionsLoading ? (
                <div style={styles.loading}>Loading versions...</div>
              ) : (
                <table style={styles.versionTable}>
                  <thead>
                    <tr>
                      <th style={styles.th}>Version</th>
                      <th style={styles.th}>Status</th>
                      <th style={styles.th}>Filename</th>
                      <th style={styles.th}>Uploaded</th>
                      <th style={styles.th}>Approved By</th>
                      <th style={styles.th}>Approved At</th>
                      <th style={styles.th}>Note</th>
                    </tr>
                  </thead>
                  <tbody>
                    {versions.versions.map((v) => (
                      <tr key={v.id} style={styles.tr}>
                        <td style={styles.td}>v{v.version_number}</td>
                        <td style={styles.td}>
                          <span style={{
                            ...styles.statusBadge,
                            backgroundColor: v.status === 'approved' ? '#dcfce7' :
                              v.status === 'pending' ? '#fef3c7' :
                                v.status === 'rejected' ? '#fee2e2' : '#f3f4f6',
                            color: v.status === 'approved' ? '#16a34a' :
                              v.status === 'pending' ? '#f59e0b' :
                                v.status === 'rejected' ? '#dc2626' : '#6b7280'
                          }}>
                            {v.status}
                          </span>
                        </td>
                        <td style={styles.td}>{v.original_filename}</td>
                        <td style={styles.td}>{new Date(v.created_at).toLocaleString()}</td>
                        <td style={styles.td}>{v.approved_by ? 'Yes' : '—'}</td>
                        <td style={styles.td}>{v.approved_at ? new Date(v.approved_at).toLocaleString() : '—'}</td>
                        <td style={styles.td}>{v.decision_note || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            <div style={styles.modalFooter}>
              <Button onClick={() => setShowVersionHistory(false)}>Close</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { display: 'flex', alignItems: 'center', gap: '8px' },
  actionGroup: { display: 'flex', gap: '8px' },
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
    maxWidth: '480px',
    boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)',
    overflow: 'hidden',
  },
  modalWide: {
    background: 'white',
    borderRadius: '12px',
    width: '100%',
    maxWidth: '900px',
    maxHeight: '80vh',
    boxShadow: '0 20px 25px -5px rgb(0 0 0 / 0.1)',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
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
  modalBody: { padding: '24px', overflowY: 'auto' },
  textarea: {
    width: '100%',
    padding: '8px 12px',
    border: '1px solid #cbd5e1',
    borderRadius: '6px',
    fontSize: '14px',
    fontFamily: 'inherit',
    resize: 'vertical',
    marginBottom: '16px',
  },
  versionTable: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: '12px',
  },
  th: {
    textAlign: 'left',
    padding: '8px 12px',
    borderBottom: '2px solid #e2e8f0',
    fontWeight: 600,
    color: '#334155',
    whiteSpace: 'nowrap',
  },
  tr: { borderBottom: '1px solid #e2e8f0' },
  td: { padding: '8px 12px', color: '#1e293b', whiteSpace: 'nowrap' },
  statusBadge: {
    fontSize: '11px',
    fontWeight: 600,
    padding: '2px 8px',
    borderRadius: '4px',
    textTransform: 'capitalize',
  },
  loading: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '24px',
    color: '#64748b',
  },
  modalFooter: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '12px',
    padding: '16px 24px',
    borderTop: '1px solid #e2e8f0',
  },
};