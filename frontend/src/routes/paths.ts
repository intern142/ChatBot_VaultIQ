export const PATHS = {
  login: '/login',
  home: '/',
  documents: '/documents',
  storage: '/storage',
  tenants: '/admin/tenants',
  audit: (tenantId: string) => `/admin/tenants/${tenantId}/audit`,
  inviteAccept: '/invite/accept',
} as const;

export type PathKey = keyof typeof PATHS;

export function isPublicPath(pathname: string): boolean {
  return pathname === PATHS.login || pathname.startsWith(PATHS.inviteAccept);
}