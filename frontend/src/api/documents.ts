import { request, buildUrl } from './client';
import type {
  DocumentResponse,
  DocumentListResponse,
  StorageUsageResponse,
  PreviewResponse,
} from './types';

export const listDocuments = (page = 1, pageSize = 20) =>
  request<DocumentListResponse>('/documents', {
    params: { page, page_size: pageSize },
  });

export const uploadDocument = (file: File) => {
  const fd = new FormData();
  fd.append('file', file);
  return request<DocumentResponse>('/documents', {
    method: 'POST',
    body: fd,
  });
};

export const previewDocument = (id: string) =>
  request<PreviewResponse>(`/documents/${id}/preview`);

export const downloadDocument = async (id: string): Promise<Blob> => {
  const token = localStorage.getItem('vaultiq_token');
  const res = await fetch(buildUrl(`/documents/${id}/download`), {
    headers: { Authorization: `Bearer ${token}` },
    credentials: 'omit',
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    const { normaliseError } = await import('./errors');
    throw normaliseError(res.status, data);
  }
  return res.blob();
};

export const deleteDocument = (id: string) =>
  request<void>(`/documents/${id}`, { method: 'DELETE' });

export const getStorageUsage = () =>
  request<StorageUsageResponse>('/documents/usage');