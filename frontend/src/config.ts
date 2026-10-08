export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';

export const ALLOWED_MIME_TYPES = [
  'application/pdf',
  'text/plain',
  'text/markdown',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/csv',
  'application/vnd.oasis.opendocument.text',
  'application/vnd.oasis.opendocument.spreadsheet',
  'application/epub+zip',
  'message/rfc822',
  'image/png',
  'image/jpeg',
  'image/tiff',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/vnd.ms-powerpoint',
  'application/vnd.oasis.opendocument.presentation',
  'application/x-ole-storage',
] as const;

export const SYSTEM_ALLOWED_FORMATS = ALLOWED_MIME_TYPES;

export const MAX_FILE_SIZE_MB = 50;
export const MAX_PAGE_SIZE = 100;

export const ROUTES = {
  login: '/login',
  home: '/',
  documents: '/documents',
  storage: '/storage',
  tenants: '/admin/tenants',
  audit: (tenantId: string) => `/admin/tenants/${tenantId}/audit`,
  inviteAccept: '/invite/accept',
  notFound: '*',
} as const;