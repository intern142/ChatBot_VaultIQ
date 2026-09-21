/*
 * Mock token utilities — fake JWT-shaped tokens with expiry, so the mock
 * exercises the same "expired / invalid token" error paths a real IdP does.
 */
import { UserInfo, ApiError } from '../types';

export interface TokenPayload extends UserInfo {
  sub: string;
  iat: number;
  exp: number;
}

export const ACCESS_TTL_S = 15 * 60; // 15 min
export const REFRESH_TTL_S = 7 * 24 * 60 * 60; // 7 days

let tokenCounter = 0;

function b64(obj: object): string {
  const json = JSON.stringify(obj);
  return btoa(unescape(encodeURIComponent(json))).replace(/=+$/, '');
}

function unb64<T>(part: string): T {
  const pad = part.length % 4 === 0 ? part : part + '='.repeat(4 - (part.length % 4));
  const json = decodeURIComponent(escape(atob(pad)));
  return JSON.parse(json) as T;
}

function nextCounter(): number {
  return ++tokenCounter;
}

export function createAccessToken(user: UserInfo, sub: string): { token: string; payload: TokenPayload } {
  const now = Math.floor(Date.now() / 1000);
  const payload: TokenPayload = {
    sub,
    name: user.name,
    role: user.role,
    organization: user.organization,
    email: user.email,
    iat: now,
    exp: now + ACCESS_TTL_S,
    jti: `${now}-${nextCounter()}`,
  };
  const header = b64({ alg: 'HS256', typ: 'JWT' });
  const token = `${header}.${b64(payload)}.mock-signature`;
  return { token, payload };
}

export function createRefreshToken(user: UserInfo, sub: string): { token: string; payload: TokenPayload } {
  const now = Math.floor(Date.now() / 1000);
  const payload: TokenPayload = {
    sub,
    name: user.name,
    role: user.role,
    organization: user.organization,
    email: user.email,
    iat: now,
    exp: now + REFRESH_TTL_S,
    jti: `${now}-${nextCounter()}`,
  };
  return { token: `${b64({ typ: 'refresh' })}.${b64(payload)}.mock-signature`, payload };
}

/** Decode + validate an access token. Throws SESSION_EXPIRED on any failure. */
export function decodeAccessToken(token: string | undefined): TokenPayload {
  if (!token || token.split('.').length !== 3) {
    throw new ApiError(401, 'Session expired', 'SESSION_EXPIRED');
  }
  try {
    const payload = unb64<TokenPayload>(token.split('.')[1]);
    if (typeof payload.exp !== 'number' || payload.exp * 1000 < Date.now()) {
      throw new ApiError(401, 'Session expired', 'SESSION_EXPIRED');
    }
    return payload;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(401, 'Session expired', 'SESSION_EXPIRED');
  }
}