import { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { UserTable } from '@/components/users/UserTable';
import { UserInviteDialog } from '@/components/users/UserInviteDialog';
import { UserImportDialog } from '@/components/users/UserImportDialog';
import { Alert } from '@/components/ui/Alert';
import { useUserManagement } from '@/hooks/useUsers';
import type { UserInviteCreate, UserInviteIssued, ImportResponse } from '@/api/types';

export default function UserManagementPage() {
  const { role } = useAuth();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const {
    invite,
    importCsv,
    deactivate,
    reactivate,
    changeRole,
    requestPasswordReset,
    loading: apiLoading,
    error: apiError,
    clearError,
  } = useUserManagement();

  useEffect(() => {
    setLoading(false);
  }, []);

  const handleInvite = () => {
    setInviteOpen(true);
  };

  const handleImport = () => {
    setImportOpen(true);
  };

  const handleInviteSubmit = async (data: UserInviteCreate): Promise<UserInviteIssued | null> => {
    const result = await invite(data);
    if (result) {
      setInviteOpen(false);
      alert(`Invitation sent!\n\nCode: ${result.code}\nEmail: ${result.email}\nRole: ${result.role}\nExpires: ${new Date(result.expires_at).toLocaleString()}\n\nShare this code with the user. It cannot be retrieved again.`);
    }
    return result;
  };

  const handleImportSubmit = async (file: File): Promise<ImportResponse | null> => {
    const result = await importCsv(file);
    if (result) {
      setImportOpen(false);
      if (result.applied) {
        alert(`Import successful!\n\n${result.message}\n\nCreated: ${result.created_count}\nInvalid: ${result.invalid_count}`);
      } else {
        alert(`Import failed:\n\n${result.message}\n\nInvalid rows: ${result.invalid_count}`);
      }
    }
    return result;
  };

  const handleDeactivate = async (user: any) => {
    if (!window.confirm(`Deactivate ${user.email}? This will revoke all their sessions.`)) return;
    try {
      await deactivate(user.id);
      alert('User deactivated successfully');
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleReactivate = async (user: any) => {
    if (!window.confirm(`Reactivate ${user.email}? They will be able to log in again.`)) return;
    try {
      await reactivate(user.id);
      alert('User reactivated successfully');
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleRoleChange = async (user: any, newRole: string) => {
    const password = prompt('Enter your current password to confirm role change:');
    if (!password) return;
    try {
      await changeRole(user.id, { role: newRole as 'employee' | 'client_admin', current_password: password });
      alert(`Role changed to ${newRole}`);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handlePasswordReset = async (user: any) => {
    if (!window.confirm(`Issue a password reset code for ${user.email}? The code will be displayed once and cannot be retrieved again.`)) return;
    try {
      const result = await requestPasswordReset(user.id);
      if (result) {
        alert(`Password reset code issued!\n\nCode: ${result.reset_code}\nExpires: ${new Date(result.expires_at).toLocaleString()}\n\nShare this code with the user. It cannot be retrieved again.`);
      }
    } catch (err: any) {
      setError(err.message);
    }
  };

  const isClientAdmin = role === 'client_admin';

  if (!isClientAdmin) {
    return (
      <div style={styles.container}>
        <div style={styles.accessDenied}>
          <h2>Access Denied</h2>
          <p>Only Client Admins can access user management.</p>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>User Management</h1>
          <p style={styles.subtitle}>Manage users in your organization</p>
        </div>
      </div>

      {error && <Alert variant="error" onDismiss={clearError}>{error}</Alert>}
      {apiError && <Alert variant="error" onDismiss={clearError}>{apiError}</Alert>}

      <div style={styles.content}>
        <UserTable
          users={[]}
          onInvite={handleInvite}
          onImport={handleImport}
          onDeactivate={handleDeactivate}
          onReactivate={handleReactivate}
          onRoleChange={handleRoleChange}
          onPasswordReset={handlePasswordReset}
          loading={loading || apiLoading}
          error={error}
          onClearError={clearError}
        />

        <UserInviteDialog
          open={inviteOpen}
          onClose={() => setInviteOpen(false)}
          onSubmit={handleInviteSubmit}
        />

        <UserImportDialog
          open={importOpen}
          onClose={() => setImportOpen(false)}
          onSubmit={handleImportSubmit}
        />
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { padding: '24px', maxWidth: '1200px', margin: '0 auto' },
  header: {
    marginBottom: '24px',
  },
  title: { margin: '0 0 8px', fontSize: '24px', fontWeight: 700, color: '#0f172a' },
  subtitle: { margin: 0, fontSize: '14px', color: '#64748b' },
  content: { padding: '24px', background: 'white', borderRadius: '12px', border: '1px solid #e2e8f0' },
  accessDenied: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '400px',
    textAlign: 'center',
    color: '#64748b',
  },
};