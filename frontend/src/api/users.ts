import { request } from './client';
import type {
  UserInviteCreate,
  UserInviteIssued,
  ImportResponse,
  DeactivateResponse,
  ReactivateResponse,
  RoleChangeRequest,
  RoleChangeResponse,
  AuditLogResponse,
  PasswordResetIssued,
} from './types';

export const inviteUser = (body: UserInviteCreate) =>
  request<UserInviteIssued>('/users/invites', {
    method: 'POST',
    body: JSON.stringify(body),
  });

export const importUsers = (file: File) => {
  const fd = new FormData();
  fd.append('file', file);
  return request<ImportResponse>('/users/import', {
    method: 'POST',
    body: fd,
  });
};

export const deactivateUser = (userId: string) =>
  request<DeactivateResponse>(`/users/${userId}/deactivate`, {
    method: 'POST',
  });

export const reactivateUser = (userId: string) =>
  request<ReactivateResponse>(`/users/${userId}/reactivate`, {
    method: 'POST',
  });

export const changeUserRole = (userId: string, body: RoleChangeRequest) =>
  request<RoleChangeResponse>(`/users/${userId}/role`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });

export const getUserAudit = (limit = 200) =>
  request<AuditLogResponse[]>(`/users/audit`, {
    params: { limit },
  });

export const issuePasswordReset = (userId: string) =>
  request<PasswordResetIssued>(`/users/${userId}/password-reset`, {
    method: 'POST',
  });