export interface MockUser {
  sub: string;
  username: string;
  email: string;
  password: string;
  role: string;
  name: string;
  tenant_id: string | null;
}

export interface MockTenant {
  id: string;
  short_code: string;
  name: string;
  status: 'active' | 'suspended' | 'offboarding' | 'purged';
  storage_quota_gb: number;
  storage_used_gb: number;
  created_at: string;
  updated_at: string;
}

const seedUsers: MockUser[] = [
  { sub: 'u-sa', username: 'admin', email: 'admin@acme.com', password: 'Admin@123', role: 'super_admin', name: 'System Admin', tenant_id: null },
  { sub: 'u-ca', username: 'cadmin', email: 'cadmin@acme.com', password: 'Client@123', role: 'client_admin', name: 'Client Admin', tenant_id: 't-1' },
  { sub: 'u-emp', username: 'employee', email: 'employee@acme.com', password: 'Employee@123', role: 'employee', name: 'Employee One', tenant_id: 't-1' },
  { sub: 'u-ba', username: 'beta', email: 'beta@betalabs.com', password: 'Beta@123', role: 'client_admin', name: 'Beta Admin', tenant_id: 't-2' },
  { sub: 'u-be', username: 'bemployee', email: 'bemp@betalabs.com', password: 'BEmployee@123', role: 'employee', name: 'Beta Employee', tenant_id: 't-2' },
];

const seedTenants: MockTenant[] = [
  { id: 't-1', short_code: 'ACME', name: 'Acme Corporation', status: 'active', storage_quota_gb: 50, storage_used_gb: 12.5, created_at: new Date(Date.now() - 86400000 * 30).toISOString(), updated_at: new Date(Date.now() - 86400000 * 5).toISOString() },
  { id: 't-2', short_code: 'BETA', name: 'Beta Labs Inc', status: 'active', storage_quota_gb: 20, storage_used_gb: 5.2, created_at: new Date(Date.now() - 86400000 * 60).toISOString(), updated_at: new Date(Date.now() - 86400000 * 10).toISOString() },
];

const sessions = new Map<string, { refreshToken: string; user: MockUser; refreshExp: number }>();
let nextSub = 1000;

const getOrgByUser = (user: MockUser): string => {
  const orgMap: Record<string, string> = { 'u-sa': 'Acme Corp', 'u-ca': 'Acme Corp', 'u-emp': 'Acme Corp', 'u-ba': 'Beta Labs', 'u-be': 'Beta Labs' };
  return orgMap[user.sub] ?? '';
};

export const mockDb = {
  findOrg(): MockUser[] | undefined { return seedUsers.length > 0 ? seedUsers : undefined; },
  findUser(email: string, username: string): MockUser | undefined {
    return seedUsers.find(u => u.email.toLowerCase() === email.toLowerCase() && u.username.toLowerCase() === username.toLowerCase());
  },
  findUserByEmailInOrg(orgCode: string, email: string): MockUser | undefined {
    return seedUsers.find(u => u.email.toLowerCase() === email.toLowerCase());
  },
  findUserBySub(sub: string): MockUser | undefined {
    return seedUsers.find(u => u.sub === sub);
  },
  addUser(orgCode: string, user: Omit<MockUser, 'sub'>): MockUser {
    const record: MockUser = { ...user, sub: `u-${nextSub++}` };
    seedUsers.push(record);
    return record;
  },
  saveSession(refreshToken: string, user: MockUser, refreshExp: number): void { sessions.set(refreshToken, { refreshToken, user, refreshExp }); },
  getSession(refreshToken: string | undefined): { refreshToken: string; user: MockUser; refreshExp: number } | null {
    if (!refreshToken) return null;
    const session = sessions.get(refreshToken);
    if (!session) return null;
    if (session.refreshExp * 1000 < Date.now()) { sessions.delete(refreshToken); return null; }
    return session;
  },
  revokeSession(refreshToken: string | undefined): void { if (refreshToken) sessions.delete(refreshToken); },
  toUserInfo(user: MockUser): { name: string; role: string; organization: string; email: string } {
    return { name: user.name, role: user.role, organization: getOrgByUser(user), email: user.email };
  },
  getTenants(): MockTenant[] { return [...seedTenants]; },
  getTenantById(id: string): MockTenant | undefined { return seedTenants.find(t => t.id === id); },
  getTenantByShortCode(short_code: string): MockTenant | undefined { return seedTenants.find(t => t.short_code === short_code); },
  getTenantForUser(user: MockUser): MockTenant | undefined {
    if (!user.tenant_id) return undefined;
    return seedTenants.find(t => t.id === user.tenant_id);
  },
  createTenant(data: { short_code: string; name: string; storage_quota_gb: number; admin_email: string }): { tenant: MockTenant; admin_invite_token: string; invite_url: string } {
    const now = new Date().toISOString();
    const admin_invite_token = `invite-${crypto.randomUUID()}`;
    const tenant: MockTenant = {
      id: `t-${seedTenants.length + 1}`,
      short_code: data.short_code,
      name: data.name,
      status: 'active',
      storage_quota_gb: data.storage_quota_gb,
      storage_used_gb: 0,
      created_at: now,
      updated_at: now,
    };
    seedTenants.unshift(tenant);
    return { tenant, admin_invite_token, invite_url: `/register?invite=${admin_invite_token}&email=${encodeURIComponent(data.admin_email)}` };
  },
  updateTenant(id: string, data: Partial<MockTenant>): MockTenant | undefined {
    const idx = seedTenants.findIndex(t => t.id === id);
    if (idx === -1) return undefined;
    seedTenants[idx] = { ...seedTenants[idx], ...data, updated_at: new Date().toISOString() };
    return seedTenants[idx];
  },
  suspendTenant(id: string): MockTenant | undefined { return this.updateTenant(id, { status: 'suspended' }); },
  reactivateTenant(id: string): MockTenant | undefined { return this.updateTenant(id, { status: 'active' }); },
  getTenantQuota(tenantId: string): { used_gb: number; total_gb: number } | undefined {
    const t = seedTenants.find(t => t.id === tenantId);
    if (!t) return undefined;
    return { used_gb: t.storage_used_gb, total_gb: t.storage_quota_gb };
  },
};