/*
 * Mock endpoint handlers — implement the backend API contract exactly:
 * request shapes, response shapes, and error responses.
 *
 * Error responses are thrown as `ApiError(status, message, code)`; the API
 * driver layers normalize everything into { error: { status, code, message } }
 * — JSON bodies for `real` mode, thrown ApiError for `mock` mode.
 */
import { ApiError, LoginRequest, RegisterRequest, LoginResponse, RefreshResponse, VerifyResponse, SuperAdminStats } from '../types';
import { mockDb } from './db';
import { createAccessToken, createRefreshToken, decodeAccessToken, REFRESH_TTL_S } from './tokens';

const ERR_INVALID = 'Invalid credentials';
const ERR_SESSION = 'Session expired';

export function handleLogin(data: LoginRequest): LoginResponse {
  const org = mockDb.findOrg(data.orgCode);
  const user = org && mockDb.findUser(data.email, data.username);
  
  // Check if user exists with correct credentials in ANY org (for "Permission denied" case)
  const userInAnyOrg = mockDb.findUser(data.email, data.username);
  const credentialsMatch = userInAnyOrg && userInAnyOrg.password === data.password;

  if (!org) {
    if (credentialsMatch) {
      // User exists with correct credentials but in a different org
      throw new ApiError(403, 'Permission denied. Invalid organization code.', 'PERMISSION_DENIED');
    }
    throw new ApiError(401, ERR_INVALID, 'INVALID_CREDENTIALS');
  }

  if (!user || user.password !== data.password) {
    throw new ApiError(401, ERR_INVALID, 'INVALID_CREDENTIALS');
  }

  // userType is mutually exclusive and must match the account role.
  if (data.userType) {
    const expected = data.userType === 'admin' ? 'client-admin' : data.userType;
    if (expected !== user.role) {
      throw new ApiError(401, ERR_INVALID, 'INVALID_CREDENTIALS');
    }
  }

  const info = mockDb.toUserInfo(user);
  const access = createAccessToken(info, user.sub);
  const refresh = createRefreshToken(info, user.sub);
  mockDb.saveSession(refresh.token, user, refresh.payload.exp);

  return { accessToken: access.token, refreshToken: refresh.token, user: info };
}

export function handleRegister(data: RegisterRequest): LoginResponse {
  const org = mockDb.findOrg(data.orgCode);
  if (!org) {
    throw new ApiError(401, ERR_INVALID, 'INVALID_CREDENTIALS');
  }

  if (mockDb.findUserByEmailInOrg(data.orgCode, data.email)) {
    throw new ApiError(409, 'Email already registered', 'EMAIL_EXISTS');
  }

  // Mirrors a sane backend policy: platform super-admins cannot self-signup.
  if (data.role === 'super-admin') {
    throw new ApiError(403, 'Super admin signup is disabled', 'SUPER_ADMIN_DISABLED');
  }

  const username = data.email.split('@')[0];
  const name = username.charAt(0).toUpperCase() + username.slice(1);
  const user = mockDb.addUser(data.orgCode, {
    username,
    email: data.email,
    password: data.password,
    role: data.role,
    name,
  });

  const info = mockDb.toUserInfo(user);
  const access = createAccessToken(info, user.sub);
  const refresh = createRefreshToken(info, user.sub);
  mockDb.saveSession(refresh.token, user, refresh.payload.exp);

  return { accessToken: access.token, refreshToken: refresh.token, user: info };
}

export function handleRefresh(refreshToken: string | undefined): RefreshResponse {
  const session = mockDb.getSession(refreshToken);
  if (!session) {
    throw new ApiError(401, ERR_SESSION, 'SESSION_EXPIRED');
  }
  // Rotate: old refresh token is invalidated, a fresh pair is issued.
  mockDb.revokeSession(refreshToken);
  const info = mockDb.toUserInfo(session.user);
  const access = createAccessToken(info, session.user.sub);
  const refresh = createRefreshToken(info, session.user.sub);
  mockDb.saveSession(refresh.token, session.user, refresh.payload.exp);
  return { accessToken: access.token, refreshToken: refresh.token };
}

export function handleLogout(refreshToken: string | undefined): VerifyResponse {
  mockDb.revokeSession(refreshToken);
  return { ok: true };
}

export function handleVerify(accessToken: string | undefined): VerifyResponse {
  decodeAccessToken(accessToken);
  return { ok: true };
}

export function handleGetSuperAdminStats(): SuperAdminStats {
  const allUsers = mockDb.organizations.flatMap(o => o.users);
  const totalUsers = allUsers.length;
  const totalOrganizations = mockDb.organizations.length;
  // Mock: consider all users as active for now
  const activeUsers = totalUsers;
  // Mock document counts (placeholder - would come from document service in real backend)
  const totalDocuments = 156;
  const pendingApproval = 12;
  const approvedDocuments = 134;

  return {
    totalUsers,
    totalOrganizations,
    activeUsers,
    totalDocuments,
    pendingApproval,
    approvedDocuments,
  };
}

export { REFRESH_TTL_S };