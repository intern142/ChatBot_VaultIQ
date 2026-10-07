export const PATHS = {
  login: '/login',
  home: '/',
  documents: '/documents',
  storage: '/storage',
  tenants: '/admin/tenants',
  audit: (tenantId: string) => `/admin/tenants/${tenantId}/audit`,
  inviteAccept: '/invite/accept',
  // Sprint 3 routes
  users: '/users',
  search: '/search',
  answers: '/answers',
  settings: '/settings',
  resetPassword: '/reset-password',
  dashboard: '/',
  dashboardOverview: '/dashboard/overview',
  dashboardOverview30d: '/dashboard/overview/30d',
  dashboardDocuments: '/dashboard/documents',
  dashboardUsers: '/dashboard/users',
  dashboardAudit: '/dashboard/audit',
  dashboardFeedback: '/dashboard/feedback',
  dashboardKnowledgeGaps: '/dashboard/knowledge-gaps',
  dashboardExport: (entity: string) => `/dashboard/export/${entity}`,
  tenantSettings: '/tenant/settings',
  tenantSettingsLogo: '/tenant/settings/logo',
  tenantPublic: (shortCode: string) => `/tenants/${shortCode}/public`,
  adminPlatformOverview: '/admin/platform/overview',
  adminPlatformOverviewDetail: (tenantId: string) => `/admin/platform/overview/${tenantId}`,
  adminPlatformHealth: '/admin/platform/health',
  adminPlatformStats: '/admin/platform/stats',
} as const;

export type PathKey = keyof typeof PATHS;

export function isPublicPath(pathname: string): boolean {
  return pathname === PATHS.login || pathname.startsWith(PATHS.inviteAccept) || pathname.startsWith(PATHS.resetPassword);
}