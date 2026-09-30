import { useState, useCallback } from 'react';
import { uploadDocument } from '../api/documents';
import type { DocumentResponse } from '../api/types';

export function useUpload() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  const upload = useCallback(async (file: File): Promise<DocumentResponse | null> => {
    setLoading(true);
    setError(null);
    setProgress(0);
    try {
      // Simulate progress since fetch doesn't support progress natively
      const progressInterval = setInterval(() => {
        setProgress((p) => Math.min(p + 10, 90));
      }, 100);

      const result = await uploadDocument(file);
      clearInterval(progressInterval);
      setProgress(100);
      return result;
    } catch (err: any) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
      setProgress(0);
    }
  }, []);

  return { upload, loading, error, progress };
}