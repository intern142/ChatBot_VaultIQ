/*
 * In-memory mock database: organizations, users, tenants, and refresh-token sessions.
 * Mirrors the backend interface spec. Seed data is used by login/register
 * flows and by the test suite (see src/api/__tests__).
 */
import { UserInfo, Tenant, TenantCreateRequest, TenantCreateResponse } from '../types';

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

export type DocumentStatus = 'pending' | 'approved' | 'rejected';

export interface MockDocument {
  id: string;
  orgCode: string;
  name: string;
  originalName: string;
  size: number;
  mimeType: string;
  status: DocumentStatus;
  uploadedBy: string;
  uploadedAt: string;
  reviewedAt?: string;
  reviewedBy?: string;
}

export interface MockTenant {
  id: string;
  short_code: string;
  name: string;
  status: 'active' | 'suspended' | 'offboarding' | 'purged';
  storage_quota_gb: number;
  created_at: string;
  updated_at: string;
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

function seedTenants(): MockTenant[] {
  const now = new Date();
  return [
    {
      id: 't-1',
      short_code: 'ACME',
      name: 'Acme Corporation',
      status: 'active',
      storage_quota_gb: 50,
      created_at: new Date(now.getTime() - 86400000 * 30).toISOString(),
      updated_at: new Date(now.getTime() - 86400000 * 5).toISOString(),
    },
    {
      id: 't-2',
      short_code: 'BETA',
      name: 'Beta Labs Inc',
      status: 'active',
      storage_quota_gb: 20,
      created_at: new Date(now.getTime() - 86400000 * 60).toISOString(),
      updated_at: new Date(now.getTime() - 86400000 * 10).toISOString(),
    },
    {
      id: 't-3',
      short_code: 'GAMMA',
      name: 'Gamma Industries',
      status: 'suspended',
      storage_quota_gb: 10,
      created_at: new Date(now.getTime() - 86400000 * 90).toISOString(),
      updated_at: new Date(now.getTime() - 86400000 * 2).toISOString(),
    },
    {
      id: 't-4',
      short_code: 'DELTA',
      name: 'Delta Systems',
      status: 'offboarding',
      storage_quota_gb: 5,
      created_at: new Date(now.getTime() - 86400000 * 120).toISOString(),
      updated_at: new Date(now.getTime() - 86400000 * 1).toISOString(),
    },
  ];
}

function seedDocuments(): MockDocument[] {
  const now = new Date();
  return [
    { id: 'doc-1', orgCode: 'ORG-12345', name: 'Employee Handbook 2024.pdf', originalName: 'Employee Handbook 2024.pdf', size: 2457600, mimeType: 'application/pdf', status: 'approved', uploadedBy: 'u-emp', uploadedAt: new Date(now.getTime() - 86400000 * 5).toISOString(), reviewedAt: new Date(now.getTime() - 86400000 * 4).toISOString(), reviewedBy: 'u-ca' },
    { id: 'doc-2', orgCode: 'ORG-12345', name: 'Leave Policy.docx', originalName: 'Leave Policy.docx', size: 512000, mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', status: 'approved', uploadedBy: 'u-emp', uploadedAt: new Date(now.getTime() - 86400000 * 10).toISOString(), reviewedAt: new Date(now.getTime() - 86400000 * 9).toISOString(), reviewedBy: 'u-ca' },
    { id: 'doc-3', orgCode: 'ORG-12345', name: 'Security Guidelines.pdf', originalName: 'Security Guidelines.pdf', size: 1024000, mimeType: 'application/pdf', status: 'pending', uploadedBy: 'u-emp', uploadedAt: new Date(now.getTime() - 86400000 * 2).toISOString() },
    { id: 'doc-4', orgCode: 'ORG-12345', name: 'Expense Report Template.xlsx', originalName: 'Expense Report Template.xlsx', size: 256000, mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', status: 'pending', uploadedBy: 'u-ca', uploadedAt: new Date(now.getTime() - 86400000 * 1).toISOString() },
    { id: 'doc-5', orgCode: 'ORG-12345', name: 'Onboarding Checklist.txt', originalName: 'Onboarding Checklist.txt', size: 12800, mimeType: 'text/plain', status: 'approved', uploadedBy: 'u-ca', uploadedAt: new Date(now.getTime() - 86400000 * 15).toISOString(), reviewedAt: new Date(now.getTime() - 86400000 * 14).toISOString(), reviewedBy: 'u-ca' },
    { id: 'doc-6', orgCode: 'ORG-67890', name: 'Project Alpha Specs.pdf', originalName: 'Project Alpha Specs.pdf', size: 3145728, mimeType: 'application/pdf', status: 'approved', uploadedBy: 'u-ba', uploadedAt: new Date(now.getTime() - 86400000 * 3).toISOString(), reviewedAt: new Date(now.getTime() - 86400000 * 2).toISOString(), reviewedBy: 'u-ba' },
    { id: 'doc-7', orgCode: 'ORG-67890', name: 'Budget Q3.xlsx', originalName: 'Budget Q3.xlsx', size: 768000, mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', status: 'pending', uploadedBy: 'u-be', uploadedAt: new Date(now.getTime() - 86400000 * 1).toISOString() },
    { id: 'doc-8', orgCode: 'ORG-67890', name: 'Contract Template.docx', originalName: 'Contract Template.docx', size: 384000, mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', status: 'rejected', uploadedBy: 'u-be', uploadedAt: new Date(now.getTime() - 86400000 * 7).toISOString(), reviewedAt: new Date(now.getTime() - 86400000 * 6).toISOString(), reviewedBy: 'u-ba' },
  ];
}

const organizations: MockOrg[] = seed();
const documents: MockDocument[] = seedDocuments();
const tenants: MockTenant[] = seedTenants();
const sessions = new Map<string, MockSession>();
let nextSub = 1000;
let nextDocId = 9;
let nextTenantId = 5;

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

  // Document methods
  getDocuments(orgCode?: string): MockDocument[] {
    return orgCode ? documents.filter(d => d.orgCode === orgCode) : [...documents];
  },

  getDocumentById(id: string): MockDocument | undefined {
    return documents.find(d => d.id === id);
  },

  addDocument(doc: Omit<MockDocument, 'id'>): MockDocument {
    const record: MockDocument = { ...doc, id: `doc-${nextDocId++}` };
    documents.unshift(record);
    return record;
  },

  updateDocumentStatus(id: string, status: DocumentStatus, reviewedBy: string): MockDocument | undefined {
    const idx = documents.findIndex(d => d.id === id);
    if (idx === -1) return undefined;
    documents[idx] = { ...documents[idx], status, reviewedAt: new Date().toISOString(), reviewedBy };
    return documents[idx];
  },

  searchDocuments(query: string, orgCode?: string): MockDocument[] {
    const docs = this.getDocuments(orgCode);
    const q = query.toLowerCase();
    return docs.filter(d => d.name.toLowerCase().includes(q) || d.originalName.toLowerCase().includes(q));
  },

  getDocumentCounts(orgCode?: string): { total: number; pending: number; approved: number; rejected: number } {
    const docs = this.getDocuments(orgCode);
    return {
      total: docs.length,
      pending: docs.filter(d => d.status === 'pending').length,
      approved: docs.filter(d => d.status === 'approved').length,
      rejected: docs.filter(d => d.status === 'rejected').length,
    };
  },

  // Tenant methods
  getTenants(): MockTenant[] {
    return [...tenants];
  },

  getTenantById(id: string): MockTenant | undefined {
    return tenants.find(t => t.id === id);
  },

  getTenantByShortCode(short_code: string): MockTenant | undefined {
    return tenants.find(t => t.short_code === short_code);
  },

  createTenant(data: TenantCreateRequest): TenantCreateResponse {
    const now = new Date().toISOString();
    const admin_invite_token = `invite-${crypto.randomUUID()}`;
    const tenant: MockTenant = {
      id: `t-${nextTenantId++}`,
      short_code: data.short_code,
      name: data.name,
      status: 'active',
      storage_quota_gb: data.storage_quota_gb,
      created_at: now,
      updated_at: now,
    };
    tenants.unshift(tenant);
    return {
      tenant,
      admin_invite_token,
      invite_url: `/register?invite=${admin_invite_token}&email=${encodeURIComponent(data.admin_email)}`,
    };
  },

  updateTenant(id: string, data: Partial<MockTenant>): MockTenant | undefined {
    const idx = tenants.findIndex(t => t.id === id);
    if (idx === -1) return undefined;
    tenants[idx] = { ...tenants[idx], ...data, updated_at: new Date().toISOString() };
    return tenants[idx];
  },

  suspendTenant(id: string): MockTenant | undefined {
    return this.updateTenant(id, { status: 'suspended' });
  },

  reactivateTenant(id: string): MockTenant | undefined {
    return this.updateTenant(id, { status: 'active' });
  },
};