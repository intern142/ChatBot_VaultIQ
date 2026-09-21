import { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { authApi } from '../../api/auth';
import { PlusIcon, SearchIcon, FileTextIcon, ClockIcon, CheckCircleIcon, XCircleIcon } from '../../components/Icons';

export default function Documents() {
  const { user } = useAuth();
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');
  const [documents, setDocuments] = useState([]);
  const [counts, setCounts] = useState({ total: 0, pending: 0, approved: 0, rejected: 0 });
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [showUpload, setShowUpload] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const [docs, docCounts] = await Promise.all([
          authApi.getDocuments(user?.organization),
          authApi.getDocumentCounts(user?.organization),
        ]);
        setDocuments(docs);
        setCounts(docCounts);
      } catch (e) {
        console.error('Failed to fetch documents:', e);
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, [user?.organization]);

  const filteredDocs = documents.filter((doc) => {
    const matchesSearch = doc.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      doc.originalName.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesFilter = activeFilter === 'all' || doc.status === activeFilter;
    return matchesSearch && matchesFilter;
  });

  const getStatusIcon = (status) => {
    switch (status) {
      case 'pending': return <ClockIcon className="status-icon status-pending" />;
      case 'approved': return <CheckCircleIcon className="status-icon status-approved" />;
      case 'rejected': return <XCircleIcon className="status-icon status-rejected" />;
    }
  };

  const getStatusLabel = (status) => {
    switch (status) {
      case 'pending': return 'Pending Approval';
      case 'approved': return 'Approved';
      case 'rejected': return 'Rejected';
    }
  };

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!selectedFile || !user) return;
    setUploading(true);
    try {
      await authApi.uploadDocument({
        orgCode: user.organization,
        file: selectedFile,
        uploadedBy: user.email,
      });
      setShowUpload(false);
      setSelectedFile(null);
      // Refresh documents
      const [docs, docCounts] = await Promise.all([
        authApi.getDocuments(user.organization),
        authApi.getDocumentCounts(user.organization),
      ]);
      setDocuments(docs);
      setCounts(docCounts);
    } catch (e) {
      console.error('Upload failed:', e);
      alert('Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const formatDate = (iso) => new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
  });

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const filterCards = [
    { key: 'all', label: 'Total Documents', count: counts.total, icon: <FileTextIcon /> },
    { key: 'pending', label: 'Pending Approval', count: counts.pending, icon: <ClockIcon /> },
    { key: 'approved', label: 'Approved', count: counts.approved, icon: <CheckCircleIcon /> },
  ];

  if (loading) {
    return (
      <div className="page">
        <div className="dashboard-header">
          <h1 className="dashboard-title">Documents</h1>
        </div>
        <div className="stats-grid">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="stat-card">
              <h3>Loading...</h3>
              <p className="stat-value"><span className="pulse">—</span></p>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="dashboard-header">
        <h1 className="dashboard-title">Documents</h1>
      </div>

      <div className="documents-toolbar">
        <div className="search-bar-wrapper">
          <SearchIcon className="search-icon" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search documents by name..."
            className="search-input"
          />
        </div>

        <button className="primary-btn insert-doc-btn" onClick={() => setShowUpload(true)}>
          <PlusIcon /> Insert Document
        </button>
      </div>

      <div className="filter-cards">
        {filterCards.map(({ key, label, count, icon }) => (
          <button
            key={key}
            className={`filter-card ${activeFilter === key ? 'active' : ''}`}
            onClick={() => setActiveFilter(key)}
          >
            <div className="filter-icon">{icon}</div>
            <div className="filter-info">
              <span className="filter-label">{label}</span>
              <span className="filter-count">{count}</span>
            </div>
          </button>
        ))}
      </div>

      <div className="documents-table-wrapper">
        {filteredDocs.length === 0 ? (
          <div className="empty-state">
            <FileTextIcon className="empty-icon" />
            <p>{searchQuery ? 'No documents match your search.' : activeFilter === 'all' ? 'No documents uploaded yet.' : `No ${activeFilter} documents.`}</p>
          </div>
        ) : (
          <table className="documents-table">
            <thead>
              <tr>
                <th>Document Name</th>
                <th>Status</th>
                <th>Size</th>
                <th>Uploaded By</th>
                <th>Uploaded At</th>
                <th>Reviewed At</th>
              </tr>
            </thead>
            <tbody>
              {filteredDocs.map((doc) => (
                <tr key={doc.id}>
                  <td className="doc-name">{doc.name}</td>
                  <td>
                    <span className={`status-badge status-${doc.status}`}>
                      {getStatusIcon(doc.status)}
                      {getStatusLabel(doc.status)}
                    </span>
                  </td>
                  <td>{formatSize(doc.size)}</td>
                  <td>{doc.uploadedBy}</td>
                  <td>{formatDate(doc.uploadedAt)}</td>
                  <td>{doc.reviewedAt ? formatDate(doc.reviewedAt) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showUpload && (
        <div className="modal-overlay" onClick={() => setShowUpload(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Insert Document</h3>
              <button className="modal-close" onClick={() => setShowUpload(false)}>×</button>
            </div>
            <form onSubmit={handleUpload} className="modal-body">
              <div className="form-group">
                <label>Select File</label>
                <input type="file" onChange={handleFileSelect} required disabled={uploading} />
                {selectedFile && <p className="file-selected">{selectedFile.name} ({formatSize(selectedFile.size)})</p>}
              </div>
              <div className="modal-actions">
                <button type="button" className="secondary-btn" onClick={() => { setShowUpload(false); setSelectedFile(null); }}>Cancel</button>
                <button type="submit" className="primary-btn" disabled={!selectedFile || uploading}>
                  {uploading ? 'Uploading...' : 'Upload Document'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}