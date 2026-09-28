import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { TokenStore } from '../lib/TokenStore';
import api from '../api/auth';
import type { AuthUser, LoginRequest, LoginResponse } from '../api/types';

interface AuthContextType {
  user: AuthUser | null;
  loading: boolean;
  error: string | null;
  login: (data: LoginRequest) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const clearError = useCallback(() => setError(null), []);

  const bootstrap = useCallback(async () => {
    const accessToken = TokenStore.getAccess();
    if (!accessToken) {
      setLoading(false);
      return;
    }

    if (TokenStore.isAccessTokenExpired()) {
      if (TokenStore.getRefresh()) {
        try {
          await refreshToken();
          return;
        } catch {
          TokenStore.clear();
        }
      }
      setLoading(false);
      return;
    }

    try {
      await api.verify();
      if (TokenStore.shouldRefresh()) {
        refreshToken();
      }
    } catch {
      TokenStore.clear();
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshToken = async () => {
    try {
      const { accessToken, refreshToken } = await api.refresh();
      TokenStore.setTokens(accessToken, refreshToken, 86400);
    } catch {
      TokenStore.clear();
      setUser(null);
    }
  };

  useEffect(() => {
    bootstrap();
  }, [bootstrap]);

  const login = async (data: LoginRequest) => {
    setError(null);
    try {
      const res: LoginResponse = await api.login(data);
      TokenStore.setTokens(res.accessToken, res.refreshToken, 86400);
      setUser(res.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
      throw err;
    }
  };

  const logout = async () => {
    try {
      await api.logout();
    } finally {
      TokenStore.clear();
      setUser(null);
    }
  };

  return (
    <AuthContext.Provider value={{ user, loading, error, login, logout, clearError }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}