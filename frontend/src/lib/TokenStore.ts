// FE2-1: in-memory access token + persisted refresh token
const ACCESS_KEY = 'vaultiq_access';
const REFRESH_KEY = 'vaultiq_refresh';

export const TokenStore = {
  getAccess(): string | null { return sessionStorage.getItem(ACCESS_KEY); },
  setAccess(t: string) { sessionStorage.setItem(ACCESS_KEY, t); },
  clearAccess() { sessionStorage.removeItem(ACCESS_KEY); },

  getRefresh(): string | null { return localStorage.getItem(REFRESH_KEY); },
  setRefresh(t: string) { localStorage.setItem(REFRESH_KEY, t); },
  clearRefresh() { localStorage.removeItem(REFRESH_KEY); },

  clearAll() { this.clearAccess(); this.clearRefresh(); },
  hasTokens(): boolean { return !!this.getAccess() && !!this.getRefresh(); },
};