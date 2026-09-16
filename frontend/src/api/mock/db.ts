/*
 * In-memory mock database: organizations, users, and refresh-token sessions.
 * Mirrors the backend interface spec. Seed data is used by login/register
 * flows and by the test suite (see src/api/__tests__).
 */
import { UserInfo } from '../types';

export interface MockUser {
  sub: string;
  username: string;
  email: string;
  password: string;
  role: string;
  name: string;
}

export interface MockOrg {
  code: string;
  name: string;
  users: MockUser[];
}

export interface MockSession {
  refreshToken: string;
  user: MockUser;
  refreshExp: number;
}

function seed(): MockOrg[] {
  return [
    {
      code: 'ORG-12345',
      name: 'Acme Corp',
      users: [
        { sub: 'u-sa', username: 'admin', email: 'admin@acme.com', password: 'Admin@123', role: 'super-admin', name: 'System Admin' },
        { sub: 'u-ca', username: 'cadmin', email: 'cadmin@acme.com', password: 'Client@123', role: 'client-admin', name: 'Client Admin' },
        { sub: 'u-emp', username: 'employee', email: 'employee@acme.com', password: 'Employee@123', role: 'employee', name: 'Employee One' },
      ],
    },
    {
      code: 'ORG-67890',
      name: 'Beta Labs',
      users: [
        { sub: 'u-ba', username: 'beta', email: 'beta@betalabs.com', password: 'Beta@123', role: 'client-admin', name: 'Beta Admin' },
        { sub: 'u-be', username: 'bemployee', email: 'bemp@betalabs.com', password: 'BEmployee@123', role: 'employee', name: 'Beta Employee' },
      ],
    },
  ];
}

const organizations: MockOrg[] = seed();
const sessions = new Map<string, MockSession>();
let nextSub = 1000;

export const mockDb = {
  findOrg(code: string): MockOrg | undefined {
    return organizations.find((o) => o.code === code);
  },

  findUser(email: string, username: string): MockUser | undefined {
    for (const org of organizations) {
      const user = org.users.find(
        (u) => u.email.toLowerCase() === email.toLowerCase() && u.username.toLowerCase() === username.toLowerCase()
      );
      if (user) return user;
    }
    return undefined;
  },

  findUserByEmailInOrg(orgCode: string, email: string): MockUser | undefined {
    const org = this.findOrg(orgCode);
    return org?.users.find((u) => u.email.toLowerCase() === email.toLowerCase());
  },

  addUser(orgCode: string, user: Omit<MockUser, 'sub'>): MockUser {
    const org = this.findOrg(orgCode);
    if (!org) throw new Error('org-not-found');
    const record: MockUser = { ...user, sub: `u-${nextSub++}` };
    org.users.push(record);
    return record;
  },

  saveSession(refreshToken: string, user: MockUser, refreshExp: number): void {
    sessions.set(refreshToken, { refreshToken, user, refreshExp });
  },

  getSession(refreshToken: string | undefined): MockSession | null {
    if (!refreshToken) return null;
    const session = sessions.get(refreshToken);
    if (!session) {
      return null;
    }
    if (session.refreshExp * 1000 < Date.now()) {
      sessions.delete(refreshToken);
      return null;
    }
    return session;
  },

  revokeSession(refreshToken: string | undefined): void {
    if (refreshToken) sessions.delete(refreshToken);
  },

  toUserInfo(user: MockUser): UserInfo {
    const org = organizations.find((o) => o.users.some((u) => u.sub === user.sub));
    return {
      name: user.name,
      role: user.role,
      organization: org?.name ?? user.organization ?? '',
      email: user.email,
    };
  },
};