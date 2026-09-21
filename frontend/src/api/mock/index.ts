/*
 * Mock backend driver — same AuthApi contract as the real HTTP driver.
 * Reads tokens from TokenStore and renders each endpoint with simulated
 * latency so async loading states behave like production.
 */
import { TokenStore } from '../../lib/TokenStore';
import { AuthApi, LoginRequest, RegisterRequest, UploadDocumentRequest, DocumentStatus } from '../types';
import { handleLogin, handleRegister, handleRefresh, handleLogout, handleVerify, handleGetSuperAdminStats, handleGetDocuments, handleGetDocumentCounts, handleUploadDocument, handleUpdateDocumentStatus, handleSearchDocuments } from './handlers';

const LATENCY_MS = import.meta.env.MODE === 'test' ? 0 : 180;

function latency(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, LATENCY_MS));
}

async function run<T>(operation: () => T): Promise<T> {
  await latency();
  return operation();
}

export const mockAuthApi: AuthApi = {
  login: (data: LoginRequest) => run(() => handleLogin(data)),
  register: (data: RegisterRequest) => run(() => handleRegister(data)),
  refresh: () => run(() => handleRefresh(TokenStore.getRefresh() ?? undefined)),
  logout: () => run(() => handleLogout(TokenStore.getRefresh() ?? undefined)),
  verify: () => run(() => handleVerify(TokenStore.getAccess() ?? undefined)),
  getSuperAdminStats: () => run(() => handleGetSuperAdminStats()),
  getDocuments: (orgCode?: string) => run(() => handleGetDocuments(orgCode)),
  getDocumentCounts: (orgCode?: string) => run(() => handleGetDocumentCounts(orgCode)),
  uploadDocument: (data: UploadDocumentRequest) => run(() => handleUploadDocument(data)),
  updateDocumentStatus: (id: string, status: DocumentStatus, reviewedBy: string) => run(() => handleUpdateDocumentStatus(id, status, reviewedBy)),
  searchDocuments: (query: string, orgCode?: string) => run(() => handleSearchDocuments(query, orgCode)),
};