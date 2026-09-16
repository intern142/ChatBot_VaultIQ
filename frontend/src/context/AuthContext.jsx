import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { authApi } from '../api/auth';
import { TokenStore } from '../lib/TokenStore';

const AuthContext = createContext(null);

const REFRESH_THRESHOLD = 0.8; // 80% of token lifetime
const DEFAULT_TOKEN_TTL = 15 * 60 * 1000; // 15 min
const LOCKOUT_ATTEMPTS = 5;
const LOCKOUT_DURATION = 15 * 60 * 1000; // 15 min

export function AuthProvider({ children }) {
  const [role, setRole] = useState(() => localStorage.getItem('vaultiq_role') || null);
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('vaultiq_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lockoutUntil, setLockoutUntil] = useState(() => {
    const saved = localStorage.getItem('vaultiq_lockout_until');
    return saved ? parseInt(saved, 10) : 0;
  });
  const [failedAttempts, setFailedAttempts] = useState(() => {
    const saved = localStorage.getItem('vaultiq_failed_attempts');
    return saved ? parseInt(saved, 10) : 0;
  });

  const refreshTimerRef = useRef(null);
  const isRefreshingRef = useRef(false);

  const isLockedOut = Date.now() < lockoutUntil;
  const isAuthenticated = role !== null && user !== null && TokenStore.hasTokens();

  // Clear expired lockout on mount
  useEffect(() => {
    if (isLockedOut) {
      const remaining = lockoutUntil - Date.now();
      const timer = setTimeout(() => {
        setLockoutUntil(0);
        setFailedAttempts(0);
        localStorage.removeItem('vaultiq_lockout_until');
        localStorage.removeItem('vaultiq_failed_attempts');
      }, remaining);
      return () => clearTimeout(timer);
    } else if (lockoutUntil > 0) {
      setLockoutUntil(0);
      setFailedAttempts(0);
      localStorage.removeItem('vaultiq_lockout_until');
      localStorage.removeItem('vaultiq_failed_attempts');
    }
  }, [lockoutUntil]);

  // Cross-tab logout listener
  useEffect(() => {
    const handleStorage = (e) => {
      if (e.key === 'vaultiq_logout_event' && e.newValue) {
        clearSession();
      }
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  // Initialize session from stored tokens
  useEffect(() => {
    const initSession = async () => {
      if (TokenStore.hasTokens()) {
        try {
          await verifySession();
        } catch {
          clearSession();
        }
      }
      setIsLoading(false);
    };
    initSession();
  }, []);

  const clearSession = useCallback(() => {
    TokenStore.clearAll();
    localStorage.removeItem('vaultiq_role');
    localStorage.removeItem('vaultiq_user');
    setRole(null);
    setUser(null);
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
  }, []);

  const scheduleRefresh = useCallback((expiresIn = DEFAULT_TOKEN_TTL) => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    const delay = Math.floor(expiresIn * REFRESH_THRESHOLD);
    refreshTimerRef.current = setTimeout(() => {
      refreshAccessToken();
    }, delay);
  }, []);

  const refreshAccessToken = useCallback(async () => {
    if (isRefreshingRef.current || !TokenStore.getRefresh()) return;
    isRefreshingRef.current = true;
    try {
      const res = await authApi.refresh();
      TokenStore.setAccess(res.accessToken);
      TokenStore.setRefresh(res.refreshToken);
      scheduleRefresh();
    } catch {
      clearSession();
      window.location.href = `/login?next=${encodeURIComponent(window.location.pathname)}`;
    } finally {
      isRefreshingRef.current = false;
    }
  }, [clearSession, scheduleRefresh]);

  const verifySession = useCallback(async () => {
    const access = TokenStore.getAccess();
    if (!access) throw new Error('No access token');
    await authApi.verify();
  }, []);

  const handleApiError = useCallback((err, isLoginAttempt = false) => {
    if (err.message === 'LOGIN_FAILED' || err.message.includes('401') || err.message.includes('403')) {
      if (isLoginAttempt) {
        const newAttempts = failedAttempts + 1;
        setFailedAttempts(newAttempts);
        localStorage.setItem('vaultiq_failed_attempts', newAttempts.toString());
        if (newAttempts >= LOCKOUT_ATTEMPTS) {
          const until = Date.now() + LOCKOUT_DURATION;
          setLockoutUntil(until);
          localStorage.setItem('vaultiq_lockout_until', until.toString());
        }
        setError('Invalid credentials');
      } else {
        // Token expired/revoked during authenticated request
        refreshAccessToken().catch(() => {});
      }
    } else {
      setError('Invalid credentials');
    }
  }, [failedAttempts, refreshAccessToken]);

  const login = useCallback(async (orgCode, username, email, password, userType) => {
    setError(null);
    setIsLoading(true);
    try {
      const res = await authApi.login({ orgCode, username, email, password, userType });
      TokenStore.setAccess(res.accessToken);
      TokenStore.setRefresh(res.refreshToken);
      const newUser = res.user;
      setRole(newUser.role);
      setUser(newUser);
      localStorage.setItem('vaultiq_role', newUser.role);
      localStorage.setItem('vaultiq_user', JSON.stringify(newUser));
      setFailedAttempts(0);
      localStorage.removeItem('vaultiq_failed_attempts');
      setLockoutUntil(0);
      localStorage.removeItem('vaultiq_lockout_until');
      scheduleRefresh(DEFAULT_TOKEN_TTL);
      return { success: true, role: newUser.role };
    } catch (err) {
      handleApiError(err, true);
      return { success: false };
    } finally {
      setIsLoading(false);
    }
  }, [failedAttempts, handleApiError, scheduleRefresh]);

  const register = useCallback(async (orgCode, email, password, role) => {
    setError(null);
    setIsLoading(true);
    try {
      const res = await authApi.register({ orgCode, email, password, role });
      TokenStore.setAccess(res.accessToken);
      TokenStore.setRefresh(res.refreshToken);
      const newUser = res.user;
      setRole(newUser.role);
      setUser(newUser);
      localStorage.setItem('vaultiq_role', newUser.role);
      localStorage.setItem('vaultiq_user', JSON.stringify(newUser));
      setFailedAttempts(0);
      localStorage.removeItem('vaultiq_failed_attempts');
      setLockoutUntil(0);
      localStorage.removeItem('vaultiq_lockout_until');
      scheduleRefresh(DEFAULT_TOKEN_TTL);
      return { success: true, role: newUser.role };
    } catch (err) {
      handleApiError(err, true);
      return { success: false };
    } finally {
      setIsLoading(false);
    }
  }, [failedAttempts, handleApiError, scheduleRefresh]);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // ignore logout API errors
    } finally {
      clearSession();
      // Broadcast logout to other tabs
      localStorage.setItem('vaultiq_logout_event', Date.now().toString());
      window.location.href = '/login';
    }
  }, [clearSession]);

  const clearWarning = useCallback(() => {
    setFailedAttempts(0);
    localStorage.removeItem('vaultiq_failed_attempts');
  }, []);

  const value = {
    role,
    user,
    isAuthenticated,
    isLoading,
    isLockedOut,
    lockoutUntil,
    failedAttempts,
    error,
    login,
    register,
    logout,
    clearError: () => setError(null),
    clearWarning,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}