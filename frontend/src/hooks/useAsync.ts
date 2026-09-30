import { useState, useCallback } from 'react';

interface UseAsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

interface UseAsyncReturn<T> extends UseAsyncState<T> {
  execute: (...args: any[]) => Promise<T | null>;
  setData: (data: T | null) => void;
  setError: (error: string | null) => void;
  setLoading: (loading: boolean) => void;
  reset: () => void;
}

export function useAsync<T>(asyncFn: (...args: any[]) => Promise<T>): UseAsyncReturn<T> {
  const [state, setState] = useState<UseAsyncState<T>>({
    data: null,
    loading: false,
    error: null,
  });

  const execute = useCallback(
    async (...args: any[]): Promise<T | null> => {
      setState({ data: null, loading: true, error: null });
      try {
        const data = await asyncFn(...args);
        setState({ data, loading: false, error: null });
        return data;
      } catch (err: any) {
        const message = err.message || 'An error occurred';
        setState({ data: null, loading: false, error: message });
        return null;
      }
    },
    [asyncFn]
  );

  const setData = useCallback((data: T | null) => setState((s) => ({ ...s, data })), []);
  const setError = useCallback((error: string | null) => setState((s) => ({ ...s, error })), []);
  const setLoading = useCallback((loading: boolean) => setState((s) => ({ ...s, loading })), []);
  const reset = useCallback(() => setState({ data: null, loading: false, error: null }), []);

  return { ...state, execute, setData, setError, setLoading, reset };
}