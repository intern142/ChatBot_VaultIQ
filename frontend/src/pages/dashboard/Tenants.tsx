import { useState, useEffect } from 'react';
import api from '../../api/auth';
import { ProtectedRoute } from '../../components/ProtectedRoute';
import { PlusIcon, SearchIcon, EditIcon, TrashIcon, ChevronRightIcon, XIcon, LoaderIcon } from '../../components/Icons';
import type { Tenant, TenantCreateRequest, TenantStatus } from '../../api/types';

export function Tenants() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<TenantStatus | 'all'>('all');
  const [showModal, setShowModal] = useState(false);
  const [editingTenant, setEditingTenant] = useState<Tenant | null>(null);
  const [form, setForm] = useState<TenantCreateRequest>({
    short_code: '',
    name: '',
    storage_quota_gb: 10,
    admin_email: '',
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTenants = async () => {
    try {
      setLoading(true);
      const data = await api.getTenants();
      setTenants(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tenants');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTenants();
  }, []);

  const filteredTenants = tenants.filter(t => {
    const matchesSearch = t.short_code.toLowerCase().includes(search.toLowerCase()) ||
      t.name.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = statusFilter === 'all' || t.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (editingTenant) {
        await api.updateTenant(editingTenant.id, form);
      } else {
        await api.createTenant(form);
      }
      setShowModal(false);
      setEditingTenant(null);
      resetForm();
      fetchTenants();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save tenant');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (tenant: Tenant) => {
    setEditingTenant(tenant);
    setForm({
      short_code: tenant.short_code,
      name: tenant.name,
      storage_quota_gb: Math.round((tenant.storage_quota_mb ?? 10240) / 1024),
      admin_email: '',
    });
    setShowModal(true);
  };

  const handleSuspend = async (id: string) => {
    if (!confirm('Suspend this tenant?')) return;
    try {
      await api.suspendTenant(id);
      fetchTenants();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to suspend tenant');
    }
  };

  const handleReactivate = async (id: string) => {
    try {
      await api.reactivateTenant(id);
      fetchTenants();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reactivate tenant');
    }
  };

  const handleDelete = async (_id: string) => {
    if (!confirm('Delete this tenant? This action cannot be undone.')) return;
    setError('Delete not implemented in mock API');
  };

  const resetForm = () => {
    setForm({ short_code: '', name: '', storage_quota_gb: 10, admin_email: '' });
    setError(null);
  };

  const openCreateModal = () => {
    setEditingTenant(null);
    resetForm();
    setShowModal(true);
  };

  const statusBadges: Record<TenantStatus, string> = {
    active: 'badge-active',
    suspended: 'badge-suspended',
    offboarding: 'badge-offboarding',
    purged: 'badge-purged',
  };

  return (
    <ProtectedRoute allowedRoles={['super_admin']}>
      <div className="tenants-page">
        <div className="page-header">
          <div>
            <h1>Tenants</h1>
            <p>Manage tenant organizations</p>
          </div>
          <button className="btn btn-primary" onClick={openCreateModal}>
            <PlusIcon /> New Tenant
          </button>
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        <div className="card">
          <div className="card-header">
            <div className="search-filter">
              <div className="search-input">
                <SearchIcon />
                <input
                  type="text"
                  placeholder="Search tenants..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="input"
                />
              </div>
              <select
                value={statusFilter}
                onChange={e => setStatusFilter(e.target.value as TenantStatus | 'all')}
                className="input"
                style={{ width: 'auto', minWidth: '180px' }}
              >
                <option value="all">All Statuses</option>
                <option value="active">Active</option>
                <option value="suspended">Suspended</option>
                <option value="offboarding">Offboarding</option>
                <option value="purged">Purged</option>
              </select>
            </div>
          </div>

          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Short Code</th>
                  <th>Name</th>
                  <th>Status</th>
                  <th>Storage</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={6} style={{ textAlign: 'center', padding: '3rem' }}>
                      <div className="spinner" style={{ margin: '0 auto' }} />
                    </td>
                  </tr>
                ) : filteredTenants.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ textAlign: 'center', padding: '3rem', color: 'var(--color-muted)' }}>
                      No tenants found
                    </td>
                  </tr>
                ) : (
                  filteredTenants.map(tenant => (
                    <tr key={tenant.id}>
                      <td><code>{tenant.short_code}</code></td>
                      <td>{tenant.name}</td>
                      <td><span className={`badge ${statusBadges[tenant.status]}`}>{tenant.status}</span></td>
                      <td>{((tenant.storage_quota_mb ?? 0) / 1024).toFixed(1)} GB</td>
                      <td>{new Date(tenant.created_at).toLocaleDateString()}</td>
                      <td>
                        <div className="action-buttons">
                          <button className="btn btn-secondary btn-sm" onClick={() => handleEdit(tenant)} title="Edit">
                            <EditIcon />
                          </button>
                          {tenant.status === 'active' ? (
                            <button className="btn btn-secondary btn-sm" onClick={() => handleSuspend(tenant.id)} title="Suspend">
                              <TrashIcon />
                            </button>
                          ) : (
                            <button className="btn btn-secondary btn-sm" onClick={() => handleReactivate(tenant.id)} title="Reactivate">
                              <ChevronRightIcon />
                            </button>
                          )}
                          <button className="btn btn-secondary btn-sm" onClick={() => handleDelete(tenant.id)} title="Delete">
                            <TrashIcon />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {showModal && (
          <div className="modal-overlay" onClick={() => setShowModal(false)}>
            <div className="modal" onClick={e => e.stopPropagation()}>
              <div className="modal-header">
                <h2>{editingTenant ? 'Edit Tenant' : 'Create Tenant'}</h2>
                <button className="modal-close" onClick={() => setShowModal(false)}>
                  <XIcon />
                </button>
              </div>
              <form onSubmit={handleSubmit}>
                <div className="modal-body">
                  <div className="form-group">
                    <label htmlFor="short_code">Short Code</label>
                    <input
                      id="short_code"
                      type="text"
                      value={form.short_code}
                      onChange={e => setForm(f => ({ ...f, short_code: e.target.value.toUpperCase() }))}
                      className="input"
                      placeholder="ACME"
                      maxLength={50}
                      required
                      disabled={!!editingTenant}
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="name">Name</label>
                    <input
                      id="name"
                      type="text"
                      value={form.name}
                      onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                      className="input"
                      placeholder="Acme Corporation"
                      required
                    />
                  </div>
                  <div className="form-group">
                    <label htmlFor="storage_quota_gb">Storage Quota (GB)</label>
                    <input
                      id="storage_quota_gb"
                      type="number"
                      value={form.storage_quota_gb}
                      onChange={e => setForm(f => ({ ...f, storage_quota_gb: parseInt(e.target.value) || 1 }))}
                      className="input"
                      min={1}
                      required
                    />
                  </div>
                  {!editingTenant && (
                    <div className="form-group">
                      <label htmlFor="admin_email">Admin Email</label>
                      <input
                        id="admin_email"
                        type="email"
                        value={form.admin_email}
                        onChange={e => setForm(f => ({ ...f, admin_email: e.target.value }))}
                        className="input"
                        placeholder="admin@acme.com"
                        required
                      />
                    </div>
                  )}
                  {error && <div className="alert alert-error">{error}</div>}
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancel</button>
                  <button type="submit" className="btn btn-primary" disabled={submitting}>
                    {submitting ? <LoaderIcon className="spin" /> : editingTenant ? 'Update' : 'Create'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </ProtectedRoute>
  );
}