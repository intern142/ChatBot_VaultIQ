/*
 * VaultIQ API contract — shared request/response types and error model.
 * Single source of truth for both the mock backend and the real HTTP client.
 */

export interface LoginRequest {
  orgCode: string;
  username: string;
  email: string;
  password: string;
  userType: string;
}

export interface RegisterRequest {
  orgCode: string;
  email: string;
  password: string;
  role: string;
}

export interface UserInfo {
  name: string;
  role: string;
  organization: string;
  email: string;
}

export interface LoginResponse {
  accessToken: string;
  refreshToken: string;
  user: UserInfo;
}

export interface RefreshResponse {
  accessToken: string;
  refreshToken: string;
}

export interface VerifyResponse {
  ok: true;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    status: number;
  };
}

/**
 * Error thrown by every API driver (mock and real).
 * `message` always embeds the HTTP status so existing `err.message.includes('401')`
 * style checks in AuthContext keep working unchanged.
 */
export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(status: number, message: string, code?: string) {
    super(`${status} ${code ? code + ': ' : ''}${message}`);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

export type AuthApi = {
  login: (data: LoginRequest) => Promise<LoginResponse>;
  register: (data: RegisterRequest) => Promise<LoginResponse>;
  refresh: () => Promise<RefreshResponse>;
  logout: () => Promise<VerifyResponse>;
  verify: () => Promise<VerifyResponse>;
};