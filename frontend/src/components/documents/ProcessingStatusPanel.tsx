import { ProcessingStatus } from '../../api/types';

interface ProcessingStatusPanelProps {
  status: ProcessingStatus;
  error: string | null;
  startedAt: string | null;
  completedAt: string | null;
  version: number;
  onReprocess: () => void;
  isClientAdmin: boolean;
  loading?: boolean;
}

export function ProcessingStatusPanel({
  status,
  error,
  startedAt,
  completedAt,
  version,
  onReprocess,
  isClientAdmin,
  loading,
}: ProcessingStatusPanelProps) {
  const getStatusConfig = () => {
    switch (status) {
      case 'queued':
        return { label: 'Queued', color: '#6b7280', bg: '#f3f4f6', icon: '⏳' };
      case 'processing':
        return { label: 'Processing', color: '#3b82f6', bg: '#dbeafe', icon: '⚙️' };
      case 'ready':
        return { label: 'Ready', color: '#16a34a', bg: '#dcfce7', icon: '✅' };
      case 'failed':
        return { label: 'Failed', color: '#dc2626', bg: '#fee2e2', icon: '❌' };
      default:
        return { label: 'Unknown', color: '#6b7280', bg: '#f3f4f6', icon: '❓' };
    }
  };

  const config = getStatusConfig();

  const isProcessing = status === 'processing';
  const isReady = status === 'ready';
  const canShowReprocess = isClientAdmin && !isReady && !isProcessing;

  return (
    <div style={styles.panel}>
      <div style={styles.header}>
        <div style={styles.statusRow}>
          <span style={styles.icon}>{config.icon}</span>
          <span style={{ ...styles.statusBadge, backgroundColor: config.bg, color: config.color }}>
            {config.label}
          </span>
          <span style={styles.version}>v{version}</span>
        </div>
        {canShowReprocess && (
          <button
            style={styles.reprocessBtn}
            onClick={onReprocess}
            disabled={loading || isProcessing}
          >
            {loading ? 'Reprocessing…' : 'Reprocess'}
          </button>
        )}
      </div>

      <div style={styles.details}>
        <div style={styles.detailRow}>
          <span style={styles.detailLabel}>Started</span>
          <span style={styles.detailValue}>
            {startedAt ? new Date(startedAt).toLocaleString() : '—'}
          </span>
        </div>
        <div style={styles.detailRow}>
          <span style={styles.detailLabel}>Completed</span>
          <span style={styles.detailValue}>
            {completedAt ? new Date(completedAt).toLocaleString() : '—'}
          </span>
        </div>
        {error && (
          <div style={styles.errorRow}>
            <span style={styles.detailLabel}>Error</span>
            <span style={styles.errorText}>{error}</span>
          </div>
        )}
      </div>

      {isProcessing && (
        <div style={styles.progressBar}>
          <div style={styles.progressFill} />
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  panel: {
    border: '1px solid #e2e8f0',
    borderRadius: '8px',
    padding: '16px',
    backgroundColor: '#fafafa',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '12px',
  },
  statusRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  icon: { fontSize: '16px' },
  statusBadge: {
    fontSize: '12px',
    fontWeight: 600,
    padding: '4px 10px',
    borderRadius: '6px',
    textTransform: 'capitalize',
  },
  version: {
    fontSize: '12px',
    color: '#64748b',
    background: '#f1f5f9',
    padding: '2px 8px',
    borderRadius: '4px',
  },
  reprocessBtn: {
    padding: '6px 12px',
    border: '1px solid #cbd5e1',
    borderRadius: '6px',
    background: 'white',
    color: '#334155',
    fontSize: '13px',
    fontWeight: 500,
    cursor: 'pointer',
    transition: 'all 0.15s',
  },
  details: { display: 'flex', flexDirection: 'column', gap: '8px' },
  detailRow: { display: 'flex', gap: '12px', alignItems: 'flex-start' },
  detailLabel: { fontSize: '13px', color: '#64748b', minWidth: '80px', fontWeight: 500 },
  detailValue: { fontSize: '13px', color: '#1e293b' },
  errorRow: { display: 'flex', gap: '12px', alignItems: 'flex-start', paddingTop: '4px' },
  errorText: {
    fontSize: '13px',
    color: '#dc2626',
    fontFamily: 'monospace',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
  },
  progressBar: {
    marginTop: '12px',
    height: '4px',
    background: '#e2e8f0',
    borderRadius: '2px',
    overflow: 'hidden',
  },
  progressFill: {
    width: '100%',
    height: '100%',
    background: 'linear-gradient(90deg, #3b82f6, #60a5fa)',
    animation: 'pulse 1.5s ease-in-out infinite',
  },
};