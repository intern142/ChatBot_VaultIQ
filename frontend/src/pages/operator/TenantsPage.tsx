import { useEffect, useState } from 'react';
import { listTenants, createTenant, suspendTenant, reactivateTenant, inviteTenantAdmin } from '../../api/admin';
import { TenantTable } from '../../components/tenants/TenantTable';
import { CreateTenantDialog } from '../../components/tenants/CreateTenantDialog';
import { InviteDialog } from '../../components/tenants/InviteDialog';
import { Button } from '../../components/ui/Button';
import { EmptyState } from '../../components/ui/EmptyState';
import { Spinner } from '../../components/ui/Spinner';
import { Alert } from '../../components/ui/Alert';

export default function TenantsPage() {
  const [tenants, setTenants] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [inviteOpen, setInviteOpen] = useState<{ tenantId: string; tenantName: string } | null>(null);

  const fetchTenants = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listTenants();
      setTenants(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTenants();
  }, []);

  const handleCreate = async (body: { short_code: string; name: string; storage_quota_mb?: number }) => {
    try {
      await createTenant(body);
      setCreateOpen(false);
      fetchTenants();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleSuspend = async (id: string) => {
    if (!window.confirm('Suspend this tenant? All user sessions will be revoked immediately.')) return;
    try {
      await suspendTenant(id);
      fetchTenants();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleReactivate = async (id: string) => {
    try {
      await reactivateTenant(id);
      fetchTenants();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleInvite = async (tenantId: string, body: { email: string; expires_in_hours?: number }) => {
    try {
      await inviteTenantAdmin(tenantId, body);
      setInviteOpen(null);
    } catch (err: any) {
      setError(err.message);
    }
  };

  if (loading) {
    return (
      <div style={styles.center}>
        <Spinner size="lg" />
        <span>Loading tenants…</span>
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

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Tenants</h1>
          <p style={styles.subtitle}>Manage tenant organisations</p>
        </div>
        <Button onClick={() => setCreateOpen(true)} icon="➕">
          Create Tenant
        </Button>
      </div>

      {tenants.length === 0 ? (
        <EmptyState icon="🏢" title="No tenants" description="Create your first tenant organisation" action={{ label: 'Create Tenant', onClick: () => setCreateOpen(true) }} />
      ) : (
        <TenantTable
          tenants={tenants}
          onSuspend={handleSuspend}
          onReactivate={handleReactivate}
          onInvite={(tenant) => setInviteOpen({ tenantId: tenant.id, tenantName: tenant.name })}
          loading={loading}
        />
      )}

      <CreateTenantDialog open={createOpen} onClose={() => setCreateOpen(false)} onSuccess={handleCreate} />
      {inviteOpen && (
        <InviteDialog
          tenantId={inviteOpen.tenantId}
          tenantName={inviteOpen.tenantName}
          open
          onClose={() => setInviteOpen(null)}
          onSuccess={handleInvite}
        />
      )}
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