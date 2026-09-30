import { useEffect, useState } from 'react';
import { getStorageUsage } from '../../api/documents';
import { StorageUsageCard } from '../../components/documents/StorageUsageCard';
import { Spinner } from '../../components/ui/Spinner';
import { Alert } from '../../components/ui/Alert';
import { EmptyState } from '../../components/ui/EmptyState';

export default function StoragePage() {
  const [usage, setUsage] = useState<{ total_documents: number; total_size_bytes: number; total_size_mb: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    getStorageUsage()
      .then((data) => {
        if (mounted) setUsage(data);
      })
      .catch((err: any) => {
        if (mounted) setError(err.message);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => { mounted = false; };
  }, []);

  if (loading) {
    return (
      <div style={styles.center}>
        <Spinner size="lg" />
        <span>Loading storage usage…</span>
      </div>
    );
  }

  if (error) {
    return (
      <Alert variant="error" onDismiss={() => setError(null)}>
        {error}
      </Alert>
    );
  }

  if (!usage) {
    return <EmptyState icon="📊" title="No data" description="Storage usage unavailable" />;
  }

  return (
    <div style={styles.page}>
      <h1 style={styles.title}>Storage Usage</h1>
      <StorageUsageCard
        totalDocuments={usage.total_documents}
        totalSizeMb={usage.total_size_mb}
      />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { padding: '24px', maxWidth: '600px', margin: '0 auto' },
  title: { margin: '0 0 24px', fontSize: '24px', fontWeight: 700, color: '#0f172a' },
  center: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '300px',
    gap: '12px',
    color: '#64748b',
  },
};