import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { login as apiLogin, refresh, logout as apiLogout } from '../api/auth';
import type { UserRole, AuthUser } from '../api/types';
import { clearAuth, setAuth } from '../api/client';

interface AuthState {
  token: string | null;
  role: UserRole | null;
  tenantId: string | null;
  user: AuthUser | null;
  loading: boolean;
  error: string | null;
}

interface AuthContextValue extends AuthState {
  login: (tokenOrData: string | { organisation_code: string; email: string; password: string }, role?: UserRole, tenantId?: string | null) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
  bootstrap: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    token: null,
    role: null,
    tenantId: null,
    user: null,
    loading: true,
    error: null,
  });

  const clearError = useCallback(() => setState(s => ({ ...s, error: null })), []);

  const bootstrap = useCallback(async () => {
    const token = localStorage.getItem('vaultiq_token');
    if (!token) {
      setState(s => ({ ...s, loading: false }));
      return;
    }
    try {
      const { role, tenant_id } = await refresh();
      const user: AuthUser = {
        name: '',
        role,
        organization: tenant_id || '',
        email: '',
      };
      setState({
        token,
        role,
        tenantId: tenant_id,
        user,
        loading: false,
        error: null,
      });
    } catch {
      clearAuth();
      setState({
        token: null,
        role: null,
        tenantId: null,
        user: null,
        loading: false,
        error: null,
      });
    }
  }, []);

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  const login = async (
    tokenOrData: string | { organisation_code: string; email: string; password: string },
    role?: UserRole,
    tenantId?: string | null
  ) => {
    setState(s => ({ ...s, error: null }));
    try {
      if (typeof tokenOrData === 'string') {
        setState(s => ({ ...s, token: tokenOrData, role: role || null, tenantId: tenantId || null, loading: false, error: null }));
      } else {
        const res = await apiLogin(tokenOrData);
        setAuth(res.access_token, res.role, res.tenant_id);
        const user: AuthUser = {
          name: '',
          role: res.role,
          organization: res.tenant_id || '',
          email: tokenOrData.email,
        };
        setState(s => ({
          ...s,
          token: res.access_token,
          role: res.role,
          tenantId: res.tenant_id,
          user,
          loading: false,
          error: null,
        }));
      }
    } catch (err) {
      setState(s => ({ ...s, error: err instanceof Error ? err.message : 'Login failed' }));
      throw err;
    }
  };

  const logout = async () => {
    try {
      await apiLogout();
    } finally {
      clearAuth();
      setState({ token: null, role: null, tenantId: null, user: null, loading: false, error: null });
      window.location.href = '/login';
    }
  };

  return (
    <AuthContext.Provider value={{ ...state, login, bootstrap, logout, clearError }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}