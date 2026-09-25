import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { authApi } from '../../api/auth';
import { Tenant, TenantCreateRequest, TenantCreateResponse, TenantUpdateRequest } from '../../api/types';
import ConfirmDialog from '../../components/ConfirmDialog';
import {
  PlusIcon,
  EditIcon,
  PauseIcon,
  PlayIcon,
  CopyIcon,
  CheckIcon,
  AlertTriangleIcon,
  InfoIcon,
  LoaderIcon,
} from '../../components/Icons';

const statusConfig = {
  active: { label: 'Active', className: 'status-approved', icon: CheckIcon },
  suspended: { label: 'Suspended', className: 'status-pending', icon: PauseIcon },
  offboarding: { label: 'Offboarding', className: 'status-rejected', icon: AlertTriangleIcon },
  purged: { label: 'Purged', className: 'status-rejected', icon: AlertTriangleIcon },
};

export default function Tenants() {
  const { user } = useAuth();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createForm, setCreateForm] = useState<TenantCreateRequest>({
    short_code: '',
    name: '',
    storage_quota_gb: 10,
    admin_email: '',
  });
  const [createError, setCreateError] = useState<string | null>(null);
  const [createdInvite, setCreatedInvite] = useState<TenantCreateResponse | null>(null);

  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    variant: 'danger' | 'warning' | 'info';
    title: string;
    message: string;
    confirmText: string;
    onConfirm: () => void;
  } | null>(null);

  const fetchTenants = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await authApi.getTenants();
      setTenants(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tenants');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTenants();
  }, [fetchTenants]);

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);
    setCreating(true);
    try {
      const res = await authApi.createTenant(createForm);
      setCreatedInvite(res);
      setShowCreateModal(false);
      setCreateForm({ short_code: '', name: '', storage_quota_gb: 10, admin_email: '' });
      fetchTenants();
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create tenant');
    } finally {
      setCreating(false);
    }
  };

  const handleStatusChange = (tenant: Tenant, newStatus: Tenant['status']) => {
    const config = statusConfig[newStatus];
    const action = newStatus === 'active' ? 'reactivate' : 'suspend';
    setConfirmDialog({
      isOpen: true,
      variant: newStatus === 'active' ? 'info' : 'warning',
      title: `${config.label} Tenant`,
      message: `Are you sure you want to ${action} "${tenant.name}" (${tenant.short_code})? This will ${action === 'suspend' ? 'block all access for' : 'restore access for'} the tenant's users.`,
      confirmText: config.label,
      onConfirm: async () => {
        try {
          let updated;
          if (newStatus === 'active') {
            updated = await authApi.reactivateTenant(tenant.id);
          } else {
            updated = await authApi.suspendTenant(tenant.id);
          }
          setTenants(prev => prev.map(t => t.id === tenant.id ? updated : t));
        } catch (err) {
          setError(err instanceof Error ? err.message : `Failed to ${action} tenant`);
        }
        setConfirmDialog(null);
      },
    });
  };

  const handleCopyInvite = () => {
    if (!createdInvite) return;
    navigator.clipboard.writeText(createdInvite.invite_url);
  };

  const handleCloseInvite = () => {
    setCreatedInvite(null);
  };

  const StatusBadge = ({ status }: { status: Tenant['status'] }) => {
    const config = statusConfig[status];
    const Icon = config.icon;
    return (
      <span className={`status-badge status-${config.className}`}>
        <Icon className="status-icon" />
        {config.label}
      </span>
    );
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <div className="page">
      <div className="dashboard-header">
        <h1 className="dashboard-title">Tenants</h1>
        <button className="primary-btn insert-doc-btn" onClick={() => setShowCreateModal(true)}>
          <PlusIcon /> Create Tenant
        </button>
      </div>

      {createdInvite && (
        <div className="modal-overlay" onClick={handleCloseInvite} role="dialog" aria-modal="true">
          <div className="modal" style={{ maxWidth: '560px' }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">
                <span className="modal-icon" style={{ color: 'var(--success)' }}>
                  <CheckIcon />
                </span>
                Tenant Created Successfully
              </h3>
            </div>
            <div className="modal-body">
              <p className="confirm-message" style={{ marginBottom: '1rem' }}>
                <strong>{createdInvite.tenant.name}</strong> ({createdInvite.tenant.short_code}) has been created.
              </p>
              <div style={{ background: 'var(--muted)', borderRadius: 'var(--radius)', padding: '1rem', marginBottom: '1rem' }}>
                <p style={{ fontSize: '0.8rem', color: 'var(--muted-foreground)', marginBottom: '0.5rem' }}>
                  One-time Admin Invite Link (copy now — not shown again)
                </p>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <input
                    type="text"
                    value={createdInvite.invite_url}
                    readOnly
                    style={{
                      flex: 1,
                      padding: '0.5rem 0.75rem',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius)',
                      fontFamily: 'monospace',
                      fontSize: '0.8rem',
                      background: 'var(--card)',
                    }}
                  />
                  <button
                    type="button"
                    className="secondary-btn"
                    onClick={handleCopyInvite}
                    style={{ whiteSpace: 'nowrap', display: 'flex', alignItems: 'center', gap: '0.35rem' }}
                  >
                    <CopyIcon style={{ width: 16, height: 16 }} />
                    Copy
                  </button>
                </div>
                <p style={{ fontSize: '0.75rem', color: 'var(--muted-foreground)', marginTop: '0.5rem' }}>
                  Send this link to the first Client Admin. It expires in 7 days.
                </p>
              </div>
            </div>
            <div className="modal-actions">
              <button type="button" className="primary-btn" onClick={handleCloseInvite}>
                Done
              </button>
            </div>
          </div>
        </div>
      )}

      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)} role="dialog" aria-modal="true">
          <div className="modal" style={{ maxWidth: '480px' }} onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Create Tenant</h3>
              <button type="button" className="modal-close" onClick={() => setShowCreateModal(false)} disabled={creating} aria-label="Close">
                <LoaderIcon className="spin" style={{ width: 20, height: 20 }} />
              </button>
            </div>
            <form onSubmit={handleCreateSubmit}>
              <div className="modal-body">
                {createError && (
                  <div className="form-error" role="alert" style={{ marginBottom: '1rem' }}>
                    {createError}
                  </div>
                )}
                <div className="form-group">
                  <label htmlFor="short_code">Short Code</label>
                  <input
                    type="text"
                    id="short_code"
                    value={createForm.short_code}
                    onChange={e => setCreateForm(prev => ({ ...prev, short_code: e.target.value.toUpperCase() }))}
                    placeholder="ACME"
                    maxLength={50}
                    disabled={creating}
                    required
                    style={{ textTransform: 'uppercase' }}
                  />
                  <p style={{ fontSize: '0.75rem', color: 'var(--muted-foreground)', marginTop: '0.25rem' }}>
                    Unique identifier (uppercase, no spaces). Used in API paths.
                  </p>
                </div>
                <div className="form-group">
                  <label htmlFor="name">Organization Name</label>
                  <input
                    type="text"
                    id="name"
                    value={createForm.name}
                    onChange={e => setCreateForm(prev => ({ ...prev, name: e.target.value }))}
                    placeholder="Acme Corporation"
                    maxLength={255}
                    disabled={creating}
                    required
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="storage_quota_gb">Storage Quota (GB)</label>
                  <input
                    type="number"
                    id="storage_quota_gb"
                    value={createForm.storage_quota_gb}
                    onChange={e => setCreateForm(prev => ({ ...prev, storage_quota_gb: parseInt(e.target.value) || 0 }))}
                    min={1}
                    max={10000}
                    disabled={creating}
                    required
                  />
                </div>
                <div className="form-group">
                  <label htmlFor="admin_email">First Admin Email</label>
                  <input
                    type="email"
                    id="admin_email"
                    value={createForm.admin_email}
                    onChange={e => setCreateForm(prev => ({ ...prev, admin_email: e.target.value }))}
                    placeholder="admin@client.com"
                    disabled={creating}
                    required
                  />
                  <p style={{ fontSize: '0.75rem', color: 'var(--muted-foreground)', marginTop: '0.25rem' }}>
                    A one-time invite link will be generated for this email.
                  </p>
                </div>
              </div>
              <div className="modal-actions">
                <button type="button" className="secondary-btn" onClick={() => setShowCreateModal(false)} disabled={creating}>
                  Cancel
                </button>
                <button type="submit" className="primary-btn" disabled={creating || !createForm.short_code || !createForm.name || !createForm.admin_email}>
                  {creating ? (
                    <span className="btn-loading"><LoaderIcon className="spin" style={{ width: 16, height: 16 }} /> Creating…</span>
                  ) : 'Create Tenant'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {confirmDialog && (
        <ConfirmDialog
          isOpen={confirmDialog.isOpen}
          onClose={() => setConfirmDialog(null)}
          onConfirm={confirmDialog.onConfirm}
          title={confirmDialog.title}
          message={confirmDialog.message}
          variant={confirmDialog.variant}
          confirmText={confirmDialog.confirmText}
        />
      )}

      {error && (
        <div className="form-error" role="alert" style={{ marginBottom: '1.5rem' }}>
          {error}
        </div>
      )}

      <div className="documents-table-wrapper">
        <table className="documents-table" role="grid">
          <thead>
            <tr>
              <th scope="col">Code</th>
              <th scope="col">Name</th>
              <th scope="col">Status</th>
              <th scope="col">Storage Quota</th>
              <th scope="col">Created</th>
              <th scope="col">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} style={{ textAlign: 'center', padding: '3rem' }}>
                  <LoaderIcon className="spin" style={{ width: 24, height: 24, margin: '0 auto', color: 'var(--primary)' }} />
                </td>
              </tr>
            ) : tenants.length === 0 ? (
              <tr>
                <td colSpan={6} style={{ textAlign: 'center', padding: '3rem' }}>
                  <div className="empty-state" style={{ margin: 0 }}>
                    <InfoIcon className="empty-icon" />
                    <p>No tenants found.</p>
                    <button className="primary-btn" onClick={() => setShowCreateModal(true)}>
                      Create First Tenant
                    </button>
                  </div>
                </td>
              </tr>
            ) : (
              tenants.map(tenant => {
                const config = statusConfig[tenant.status];
                const canSuspend = tenant.status === 'active';
                const canReactivate = tenant.status === 'suspended';
                return (
                  <tr key={tenant.id}>
                    <td>
                      <code style={{ fontSize: '0.85rem', background: 'var(--muted)', padding: '0.15rem 0.4rem', borderRadius: 'var(--radius)' }}>
                        {tenant.short_code}
                      </code>
                    </td>
                    <td>
                      <span className="doc-name">{tenant.name}</span>
                    </td>
                    <td>
                      <StatusBadge status={tenant.status} />
                    </td>
                    <td>{tenant.storage_quota_gb} GB</td>
                    <td style={{ color: 'var(--muted-foreground)', fontSize: '0.85rem' }}>
                      {formatDate(tenant.created_at)}
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        {canSuspend && (
                          <button
                            type="button"
                            className="secondary-btn"
                            onClick={() => handleStatusChange(tenant, 'suspended')}
                            style={{ padding: '0.35rem 0.6rem', fontSize: '0.8rem' }}
                            title="Suspend tenant"
                          >
                            <PauseIcon style={{ width: 14, height: 14 }} />
                          </button>
                        )}
                        {canReactivate && (
                          <button
                            type="button"
                            className="secondary-btn"
                            onClick={() => handleStatusChange(tenant, 'active')}
                            style={{ padding: '0.35rem 0.6rem', fontSize: '0.8rem' }}
                            title="Reactivate tenant"
                          >
                            <PlayIcon style={{ width: 14, height: 14 }} />
                          </button>
                        )}
                        {(tenant.status === 'offboarding' || tenant.status === 'purged') && (
                          <span style={{ display: 'flex', alignItems: 'center', padding: '0.35rem 0.6rem', fontSize: '0.75rem', color: 'var(--muted-foreground)' }}>
                            Terminal state
                          </span>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}