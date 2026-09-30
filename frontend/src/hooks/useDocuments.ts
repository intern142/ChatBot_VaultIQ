import { useState, useEffect, useCallback } from 'react';
import { listDocuments, getStorageUsage } from '../api/documents';
import type { DocumentListResponse, StorageUsageResponse } from '../api/types';

export function useDocuments(page = 1, pageSize = 20) {
  const [data, setData] = useState<DocumentListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listDocuments(page, pageSize);
      setData(res);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  const refetch = useCallback(() => {
    fetch();
  }, [fetch]);

  return { documents: data?.documents || [], total: data?.total || 0, loading, error, refetch };
}

export function useStorageUsage() {
  const [usage, setUsage] = useState<StorageUsageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    getStorageUsage()
      .then((data) => {
        if (mounted) setUsage(data);
      })
      .catch((err: any) => {
        if (mounted) setError(err.message);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => { mounted = false; };
  }, []);

  return { usage, loading, error };
}