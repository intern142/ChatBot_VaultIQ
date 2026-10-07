import { useState, useCallback } from 'react';
import { getDocumentStatus, reprocessDocument } from '../api/documents';
import type { ProcessingStatusResponse } from '../api/types';

export function useDocumentProcessing() {
  const [status, setStatus] = useState<ProcessingStatusResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [reprocessing, setReprocessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = useCallback(async (documentId: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getDocumentStatus(documentId);
      setStatus(data);
      return data;
    } catch (err: any) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const reprocess = useCallback(async (documentId: string) => {
    setError(null);
    setReprocessing(true);
    try {
      await reprocessDocument(documentId);
      await loadStatus(documentId);
    } catch (err: any) {
      setError(err.message);
      throw err;
    } finally {
      setReprocessing(false);
    }
  }, [loadStatus]);

  const clearError = useCallback(() => setError(null), []);

  return {
    status,
    loading,
    reprocessing,
    error,
    loadStatus,
    reprocess,
    clearError,
  };
}