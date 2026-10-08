import { useState } from 'react';
import { Button } from '../ui/Button';
import { Alert } from '../ui/Alert';
import { Spinner } from '../ui/Spinner';
import { formatDate } from '../../utils/format';
import type { UserResponse, UserRole } from '../../api/types';

interface UserTableProps {
  users: UserResponse[];
  onInvite: () => void;
  onImport: () => void;
  onDeactivate: (user: UserResponse) => void;
  onReactivate: (user: UserResponse) => void;
  onRoleChange: (user: UserResponse, newRole: UserRole) => void;
  onPasswordReset: (user: UserResponse) => void;
  loading?: boolean;
  error?: string | null;
  onClearError?: () => void;
}

const ROLE_LABELS: Record<UserRole, string> = {
  super_admin: 'Super Admin',
  client_admin: 'Client Admin',
  employee: 'Employee',
};

const ROLE_BADGES: Record<UserRole, { bg: string; color: string }> = {
  super_admin: { bg: '#fef3c7', color: '#f59e0b' },
  client_admin: { bg: '#dbeafe', color: '#3b82f6' },
  employee: { bg: '#dcfce7', color: '#16a34a' },
};

const STATUS_BADGES: Record<string, { label: string; bg: string; color: string }> = {
  'true': { label: 'Active', bg: '#dcfce7', color: '#16a34a' },
  'false': { label: 'Inactive', bg: '#fee2e2', color: '#dc2626' },
};

const ROLE_OPTIONS: Array<{ value: UserRole; label: string }> = [
  { value: 'employee', label: 'Employee' },
  { value: 'client_admin', label: 'Client Admin' },
];

export function UserTable({
  users,
  onInvite,
  onImport,
  onDeactivate,
  onReactivate,
  onRoleChange,
  onPasswordReset,
  loading,
  error,
  onClearError,
}: UserTableProps) {
  const [selectedUser, setSelectedUser] = useState<UserResponse | null>(null);
  const [action, setAction] = useState<'deactivate' | 'reactivate' | 'role' | 'reset' | null>(null);
  const [confirmLoading, setConfirmLoading] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);

  const handleActionClick = (actionType: 'deactivate' | 'reactivate' | 'role' | 'reset', user: UserResponse) => {
    setSelectedUser(user);
    setAction(actionType);
    setConfirmError(null);
  };

  const handleConfirm = async () => {
    if (!selectedUser || !action) return;
    setConfirmLoading(true);
    setConfirmError(null);
    try {
      switch (action) {
        case 'deactivate':
          await onDeactivate(selectedUser);
          break;
        case 'reactivate':
          await onReactivate(selectedUser);
          break;
        case 'role':
          // Role change is handled in RoleChangeForm
          break;
        case 'reset':
          await onPasswordReset(selectedUser);
          break;
      }
      setSelectedUser(null);
      setAction(null);
    } catch (err: any) {
      setConfirmError(err.message);
    } finally {
      setConfirmLoading(false);
    }
  };

  const handleCancel = () => {
    setSelectedUser(null);
    setAction(null);
    setConfirmError(null);
  };

  const handleRoleChangeSubmit = async (newRole: UserRole) => {
    if (!selectedUser) return;
    try {
      await onRoleChange(selectedUser, newRole);
      setSelectedUser(null);
      setAction(null);
    } catch (err: any) {
      setConfirmError(err.message);
    } finally {
      setConfirmLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={styles.loading}>
        <Spinner size="lg" />
        <span>Loading users…</span>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <div style={styles.title}>
          <h2>Users</h2>
          <p>Manage users in your organization</p>
        </div>
        <div style={styles.headerActions}>
          <Button variant="outline" onClick={onImport}>
            Import CSV
          </Button>
          <Button onClick={onInvite}>
            Invite User
          </Button>
        </div>
      </div>

      {error && <Alert variant="error" onDismiss={onClearError}>{error}</Alert>}

      <div style={styles.tableWrapper}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Email</th>
              <th style={styles.th}>Role</th>
              <th style={styles.th}>Status</th>
              <th style={styles.th}>Created</th>
              <th style={styles.th}>Updated</th>
              <th style={styles.thActions}></th>
            </tr>
          </thead>
          <tbody>
            {users.length === 0 ? (
              <tr>
                <td colSpan={6} style={styles.emptyCell}>
                  <div style={styles.emptyState}>
                    <p>No users found</p>
                    <Button onClick={onInvite} size="sm">
                      Invite First User
                    </Button>
                  </div>
                </td>
              </tr>
            ) : (
              users.map((user) => (
                <tr key={user.id} style={styles.tr}>
                  <td style={styles.td}>
                    <span style={styles.email}>{user.email}</span>
                  </td>
                  <td style={styles.td}>
                    <span
                      style={{
                        ...styles.badge,
                        backgroundColor: ROLE_BADGES[user.role]?.bg || '#f3f4f6',
                        color: ROLE_BADGES[user.role]?.color || '#6b7280',
                      }}
                    >
                      {ROLE_LABELS[user.role] || user.role}
                    </span>
                  </td>
                  <td style={styles.td}>
                    <span
                      style={{
                        ...styles.badge,
                        backgroundColor: STATUS_BADGES[String(user.is_active)].bg,
                        color: STATUS_BADGES[String(user.is_active)].color,
                      }}
                    >
                      {STATUS_BADGES[String(user.is_active)].label}
                    </span>
                  </td>
                  <td style={styles.td}>{formatDate(user.created_at)}</td>
                  <td style={styles.td}>{formatDate(user.updated_at)}</td>
                  <td style={styles.tdActions}>
                    <div style={styles.rowActions}>
                      {!user.is_active && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleActionClick('reactivate', user)}
                        >
                          Reactivate
                        </Button>
                      )}
                      {user.is_active && user.role !== 'super_admin' && (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleActionClick('deactivate', user)}
                          >
                            Deactivate
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleActionClick('role', user)}
                          >
                            Change Role
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleActionClick('reset', user)}
                          >
                            Reset Password
                          </Button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {error && <Alert variant="error" onDismiss={onClearError}>{error}</Alert>}

      {selectedUser && action && (
        <div style={styles.modalOverlay} onClick={handleCancel}>
          <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
            <div style={styles.modalHeader}>
              <h4>{getActionTitle(action)} {selectedUser.email}</h4>
              <button style={styles.modalClose} onClick={handleCancel}>×</button>
            </div>
            <div style={styles.modalBody}>
              <p>{getActionMessage(action, selectedUser)}</p>
              {confirmError && <Alert variant="error">{confirmError}</Alert>}
              {action === 'role' && (
                <RoleChangeForm
                  currentRole={selectedUser.role}
                  onSubmit={handleRoleChangeSubmit}
                  loading={confirmLoading}
                />
              )}
            </div>
            <div style={styles.modalFooter}>
              <Button variant="outline" onClick={handleCancel}>
                Cancel
              </Button>
              <Button
                variant={action === 'deactivate' || action === 'reset' ? 'danger' : action === 'role' ? 'secondary' : 'primary'}
                onClick={handleConfirm}
                loading={confirmLoading}
              >
                {confirmLoading ? 'Processing…' : getActionButtonLabel(action)}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function getActionTitle(action: string): string {
  switch (action) {
    case 'deactivate': return 'Deactivate';
    case 'reactivate': return 'Reactivate';
    case 'role': return 'Change Role for';
    case 'reset': return 'Reset Password for';
    default: return 'Action';
  }
}

function getActionMessage(action: string, user: { email: string; role: string }): string {
  switch (action) {
    case 'deactivate':
      return `Are you sure you want to deactivate ${user.email}? This will revoke all their sessions.`;
    case 'reactivate':
      return `Are you sure you want to reactivate ${user.email}? They will be able to log in again.`;
    case 'role':
      return `Change role for ${user.email} (currently ${user.role}).`;
    case 'reset':
      return `Issue a password reset code for ${user.email}? The code will be displayed once and cannot be retrieved again.`;
    default:
      return '';
  }
}

function getActionButtonLabel(action: string): string {
  switch (action) {
    case 'deactivate': return 'Deactivate';
    case 'reactivate': return 'Reactivate';
    case 'role': return 'Change Role';
    case 'reset': return 'Issue Reset Code';
    default: return 'Confirm';
  }
}

interface RoleChangeFormProps {
  currentRole: UserRole;
  onSubmit: (newRole: UserRole) => Promise<void>;
  loading: boolean;
}

function RoleChangeForm({ currentRole, onSubmit, loading }: RoleChangeFormProps) {
  const [newRole, setNewRole] = useState<UserRole>(currentRole === 'client_admin' ? 'employee' : 'client_admin');
  const [password, setPassword] = useState('');
  const [passwordError, setPasswordError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);
    if (!password) {
      setPasswordError('Current password is required');
      return;
    }
    try {
      await onSubmit(newRole);
    } catch {
      // Error handled by parent
    }
  };

  return (
    <form onSubmit={handleSubmit} style={styles.form}>
      <div style={styles.formGroup}>
        <label htmlFor="new-role" style={styles.label}>
          New Role
        </label>
        <select
          id="new-role"
          value={newRole}
          onChange={(e) => setNewRole(e.target.value as UserRole)}
          style={styles.select}
          disabled={loading}
        >
          {ROLE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
      <div style={styles.formGroup}>
        <label htmlFor="current-password" style={styles.label}>
          Your Current Password (step-up)
        </label>
        <input
          id="current-password"
          type="password"
          value={password}
          onChange={(e) => { setPassword(e.target.value); setPasswordError(null); }}
          style={styles.input}
          placeholder="Enter your password"
          disabled={loading}
          required
        />
        {passwordError && <p style={styles.error}>{passwordError}</p>}
      </div>
    </form>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { padding: '24px', maxWidth: '1200px', margin: '0 auto' },
  header: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginBottom: '24px',
    gap: '16px',
  },
  title: {
    flex: 1,
  },
  headerActions: {
    display: 'flex',
    gap: '12px',
  },
  tableWrapper: { overflowX: 'auto' },
  table: { width: '100%', borderCollapse: 'collapse', fontSize: '13px' },
  th: {
    textAlign: 'left',
    padding: '12px 16px',
    borderBottom: '2px solid #e2e8f0',
    fontWeight: 600,
    color: '#334155',
    whiteSpace: 'nowrap',
  },
  thActions: { textAlign: 'right', padding: '12px 16px' },
  tr: { borderBottom: '1px solid #e2e8f0' },
  td: { padding: '12px 16px', color: '#1e293b', whiteSpace: 'nowrap' },
  tdActions: { textAlign: 'right', padding: '12px 16px' },
  email: { fontWeight: 500, maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', display: 'inline-block' },
  badge: {
    fontSize: '11px',
    fontWeight: 600,
    padding: '2px 8px',
    borderRadius: '4px',
    textTransform: 'capitalize',
    whiteSpace: 'nowrap',
  },
  rowActions: { display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '8px' },
  loading: { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px', padding: '48px', color: '#64748b' },
  emptyCell: { textAlign: 'center', padding: '48px' },
  emptyState: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', color: '#64748b' },
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
  modalBody: { padding: '24px' },
  modalFooter: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '12px',
    padding: '16px 24px',
    borderTop: '1px solid #e2e8f0',
  },
  form: { display: 'flex', flexDirection: 'column', gap: '16px' },
  formGroup: { display: 'flex', flexDirection: 'column', gap: '6px' },
  label: { fontSize: '13px', fontWeight: 500, color: '#334155' },
  select: { padding: '8px 12px', border: '1px solid #cbd5e1', borderRadius: '6px', fontSize: '14px' },
  input: { padding: '8px 12px', border: '1px solid #cbd5e1', borderRadius: '6px', fontSize: '14px' },
  error: { margin: 0, fontSize: '12px', color: '#dc2626' },
};