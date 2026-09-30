import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { refresh, logout as apiLogout } from '../api/auth';
import type { UserRole } from '../api/types';
import { getToken, clearAuth } from '../api/client';

interface AuthState {
  token: string | null;
  role: UserRole | null;
  tenantId: string | null;
  loading: boolean;
  error: string | null;
}

interface AuthContextValue extends AuthState {
  login: (token: string, role: UserRole, tenantId: string | null) => void;
  bootstrap: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    token: null,
    role: null,
    tenantId: null,
    loading: true,
    error: null,
  });

  const bootstrap = useCallback(async () => {
    const token = getToken();
    if (!token) {
      setState((s) => ({ ...s, loading: false }));
      return;
    }
    try {
      const { role, tenant_id } = await refresh();
      setState({
        token,
        role,
        tenantId: tenant_id,
        loading: false,
        error: null,
      });
    } catch {
      clearAuth();
      setState({
        token: null,
        role: null,
        tenantId: null,
        loading: false,
        error: null,
      });
    }
  }, []);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  const login = (token: string, role: UserRole, tenantId: string | null) => {
    setState({ token, role, tenantId, loading: false, error: null });
  };

  const logout = async () => {
    try {
      await apiLogout();
    } finally {
      clearAuth();
      setState({ token: null, role: null, tenantId: null, loading: false, error: null });
      window.location.href = '/login';
    }
  };

  return (
    <AuthContext.Provider value={{ ...state, login, bootstrap, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}