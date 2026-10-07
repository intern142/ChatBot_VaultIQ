import { useState, useCallback } from 'react';
import { approveDocument, rejectDocument, getVersionHistory } from '../api/documents';
import type { VersionHistoryResponse } from '../api/types';

export function useDocumentApproval() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [versions, setVersions] = useState<VersionHistoryResponse | null>(null);
  const [versionsLoading, setVersionsLoading] = useState(false);

  const approve = useCallback(async (documentId: string, note?: string) => {
    setError(null);
    setLoading(true);
    try {
      await approveDocument(documentId, { note });
    } catch (err: any) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const reject = useCallback(async (documentId: string, note?: string) => {
    setError(null);
    setLoading(true);
    try {
      await rejectDocument(documentId, { note });
    } catch (err: any) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const loadVersions = useCallback(async (documentId: string) => {
    setVersionsLoading(true);
    try {
      const data = await getVersionHistory(documentId);
      setVersions(data);
      return data;
    } catch (err: any) {
      setError(err.message);
      throw err;
    } finally {
      setVersionsLoading(false);
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return {
    approve,
    reject,
    loadVersions,
    loading,
    error,
    versions,
    versionsLoading,
    clearError,
  };
}