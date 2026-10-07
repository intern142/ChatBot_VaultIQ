import { ProcessingStatus } from '../../api/types';

interface DocumentStatusBadgeProps {
  status: string;
  processingStatus?: ProcessingStatus;
  processingError?: string | null;
}

export function DocumentStatusBadge({ status, processingStatus, processingError }: DocumentStatusBadgeProps) {
  const getStatusConfig = () => {
    switch (status) {
      case 'pending':
        return { label: 'Pending', color: '#f59e0b', bg: '#fef3c7' };
      case 'approved':
        return { label: 'Approved', color: '#16a34a', bg: '#dcfce7' };
      case 'archived':
        return { label: 'Archived', color: '#6b7280', bg: '#f3f4f6' };
      case 'rejected':
        return { label: 'Rejected', color: '#dc2626', bg: '#fee2e2' };
      default:
        return { label: status, color: '#6b7280', bg: '#f3f4f6' };
    }
  };

  const getProcessingConfig = () => {
    if (!processingStatus) return null;
    switch (processingStatus) {
      case 'queued':
        return { label: 'Queued', color: '#6b7280', bg: '#f3f4f6' };
      case 'processing':
        return { label: 'Processing', color: '#3b82f6', bg: '#dbeafe' };
      case 'ready':
        return { label: 'Ready', color: '#16a34a', bg: '#dcfce7' };
      case 'failed':
        return { label: 'Failed', color: '#dc2626', bg: '#fee2e2' };
      default:
        return null;
    }
  };

  const statusConfig = getStatusConfig();
  const processingConfig = getProcessingConfig();

  return (
    <div style={styles.container}>
      <span style={{ ...styles.badge, backgroundColor: statusConfig.bg, color: statusConfig.color }}>
        {statusConfig.label}
      </span>
      {processingConfig && (
        <span style={{ ...styles.badge, backgroundColor: processingConfig.bg, color: processingConfig.color }}>
          {processingConfig.label}
        </span>
      )}
      {processingError && (
        <span style={styles.errorBadge} title={processingError}>
          Error
        </span>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { display: 'flex', flexDirection: 'column', gap: '4px' },
  badge: {
    fontSize: '11px',
    fontWeight: 600,
    padding: '2px 8px',
    borderRadius: '4px',
    textTransform: 'capitalize',
    whiteSpace: 'nowrap',
  },
  errorBadge: {
    fontSize: '11px',
    fontWeight: 600,
    padding: '2px 8px',
    borderRadius: '4px',
    backgroundColor: '#fee2e2',
    color: '#dc2626',
    whiteSpace: 'nowrap',
  },
};