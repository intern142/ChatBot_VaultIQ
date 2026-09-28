const ACCESS_TOKEN_KEY = 'vaultiq_access_token';
const REFRESH_TOKEN_KEY = 'vaultiq_refresh_token';
const TOKEN_EXPIRY_KEY = 'vaultiq_token_expiry';

export class TokenStore {
  static getAccess(): string | null {
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  }

  static getRefresh(): string | null {
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  }

  static setTokens(accessToken: string, refreshToken: string, expiresIn: number): void {
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
    const expiry = Date.now() + expiresIn * 1000;
    localStorage.setItem(TOKEN_EXPIRY_KEY, expiry.toString());
  }

  static clear(): void {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
    localStorage.removeItem(TOKEN_EXPIRY_KEY);
  }

  static isAccessTokenExpired(): boolean {
    const expiry = localStorage.getItem(TOKEN_EXPIRY_KEY);
    if (!expiry) return true;
    return Date.now() >= parseInt(expiry, 10);
  }

  static shouldRefresh(): boolean {
    const expiry = localStorage.getItem(TOKEN_EXPIRY_KEY);
    if (!expiry) return true;
    const expiryMs = parseInt(expiry, 10);
    const eightyPercent = Date.now() + (expiryMs - Date.now()) * 0.2;
    return Date.now() >= eightyPercent;
  }
}