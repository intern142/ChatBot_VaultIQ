import { useEffect, useState } from 'react';
import { listDocuments, deleteDocument, getStorageUsage } from '../../api/documents';
import { useAuth } from '../../context/AuthContext';
import { DocumentTable } from '../../components/documents/DocumentTable';
import { UploadDialog } from '../../components/documents/UploadDialog';
import { StorageUsageCard } from '../../components/documents/StorageUsageCard';
import { Button } from '../../components/ui/Button';
import { EmptyState } from '../../components/ui/EmptyState';
import { Spinner } from '../../components/ui/Spinner';
import { Alert } from '../../components/ui/Alert';

export default function DocumentsPage() {
  const { role } = useAuth();
  const [documents, setDocuments] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const [loading, setLoading] = useState(true);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usage, setUsage] = useState<{ total_documents: number; total_size_mb: number } | null>(null);
  const [usageError, setUsageError] = useState<string | null>(null);

  const fetchDocuments = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listDocuments(page, pageSize);
      setDocuments(data.documents);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchUsage = async () => {
    if (role !== 'client_admin') return;
    try {
      const data = await getStorageUsage();
      setUsage({ total_documents: data.total_documents, total_size_mb: data.total_size_mb });
    } catch (err: any) {
      setUsageError(err.message);
    }
  };

  useEffect(() => {
    fetchDocuments();
    fetchUsage();
  }, [page, pageSize]);

  const handleDelete = async (id: string) => {
    if (!window.confirm('Delete this document? This cannot be undone.')) return;
    try {
      await deleteDocument(id);
      fetchDocuments();
      fetchUsage();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleUploadSuccess = () => {
    setUploadOpen(false);
    fetchDocuments();
    fetchUsage();
  };

  const isClientAdmin = role === 'client_admin';

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Documents</h1>
          <p style={styles.subtitle}>Manage your organisation's documents</p>
        </div>
        {isClientAdmin && (
          <Button onClick={() => setUploadOpen(true)} icon="➕">
            Upload
          </Button>
        )}
      </div>

      {error && <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>}

      {isClientAdmin && usage && (
        <StorageUsageCard
          totalDocuments={usage.total_documents}
          totalSizeMb={usage.total_size_mb}
          error={usageError}
        />
      )}

      {loading ? (
        <div style={styles.loading}>
          <Spinner size="lg" />
          <span>Loading documents…</span>
        </div>
      ) : documents.length === 0 ? (
        <EmptyState
          icon="📄"
          title="No documents yet"
          description={isClientAdmin ? 'Upload your first document to get started' : 'No documents available'}
          action={isClientAdmin ? { label: 'Upload', onClick: () => setUploadOpen(true) } : undefined}
        />
      ) : (
        <DocumentTable
          documents={documents}
          onDelete={handleDelete}
          canDelete={isClientAdmin}
          canApprove={isClientAdmin}
          canReprocess={isClientAdmin}
          loading={loading}
        />
      )}

      {total > pageSize && (
        <div style={styles.pagination}>
          <Button
            variant="outline"
            disabled={page === 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous
          </Button>
          <span style={styles.pageInfo}>
            Page {page} of {Math.ceil(total / pageSize)} ({total} total)
          </span>
          <Button
            variant="outline"
            disabled={page === Math.ceil(total / pageSize)}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      )}

      <UploadDialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onSuccess={handleUploadSuccess}
      />
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { padding: '24px', maxWidth: '1000px', margin: '0 auto' },
  header: {
    display: 'flex',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    marginBottom: '24px',
    gap: '16px',
  },
  title: { margin: '0 0 4px', fontSize: '24px', fontWeight: 700, color: '#0f172a' },
  subtitle: { margin: 0, fontSize: '14px', color: '#64748b' },
  loading: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '12px',
    padding: '48px',
    color: '#64748b',
  },
  pagination: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '16px',
    marginTop: '24px',
  },
  pageInfo: { fontSize: '14px', color: '#64748b' },
};