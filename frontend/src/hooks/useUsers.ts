import { useState, useCallback } from 'react';
import {
  inviteUser,
  importUsers,
  deactivateUser,
  reactivateUser,
  changeUserRole,
  getUserAudit,
  issuePasswordReset,
} from '../api/users';
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
} from '../api/types';

export function useUserManagement() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const invite = useCallback(async (body: UserInviteCreate): Promise<UserInviteIssued | null> => {
    setLoading(true);
    setError(null);
    try {
      const result = await inviteUser(body);
      return result;
    } catch (err: any) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const importCsv = useCallback(async (file: File): Promise<ImportResponse | null> => {
    setLoading(true);
    setError(null);
    try {
      const result = await importUsers(file);
      return result;
    } catch (err: any) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const deactivate = useCallback(async (userId: string): Promise<DeactivateResponse | null> => {
    setLoading(true);
    setError(null);
    try {
      const result = await deactivateUser(userId);
      return result;
    } catch (err: any) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const reactivate = useCallback(async (userId: string): Promise<ReactivateResponse | null> => {
    setLoading(true);
    setError(null);
    try {
      const result = await reactivateUser(userId);
      return result;
    } catch (err: any) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const changeRole = useCallback(async (userId: string, body: RoleChangeRequest): Promise<RoleChangeResponse | null> => {
    setLoading(true);
    setError(null);
    try {
      const result = await changeUserRole(userId, body);
      return result;
    } catch (err: any) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const getAudit = useCallback(async (limit = 200): Promise<AuditLogResponse[] | null> => {
    setLoading(true);
    setError(null);
    try {
      const result = await getUserAudit(limit);
      return result;
    } catch (err: any) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const requestPasswordReset = useCallback(async (userId: string): Promise<PasswordResetIssued | null> => {
    setLoading(true);
    setError(null);
    try {
      const result = await issuePasswordReset(userId);
      return result;
    } catch (err: any) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return {
    invite,
    importCsv,
    deactivate,
    reactivate,
    changeRole,
    getAudit,
    requestPasswordReset,
    loading,
    error,
    clearError,
  };
}