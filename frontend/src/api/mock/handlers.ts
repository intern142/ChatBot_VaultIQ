import type {
  LoginRequestLegacy as LoginRequest,
  LoginResponse,
  RefreshResponse,
  VerifyResponse,
  Tenant,
  TenantCreateRequest,
  TenantCreateResponse,
  TenantUpdateRequest,
  QuotaResponse,
  AuthUser,
  SearchRequest,
  SearchResponse,
  SuggestRequest,
  SuggestResponse,
  SearchResult,
  AnswerRequest,
  AnswerResponse,
  FeedbackCreate,
  FeedbackUpdate,
  FeedbackResponse,
  FeedbackListResponse,
} from '../types';
import { ApiError } from '../errors';
import { mockDb } from './db';

const LATENCY_MS = import.meta.env.MODE === 'test' ? 0 : 180;
const ERR_INVALID = 'Invalid credentials';

function latency(): Promise<void> { return new Promise(resolve => setTimeout(resolve, LATENCY_MS)); }
function run<T>(operation: () => T): Promise<T> { return latency().then(() => operation()); }

function createAccessToken(_info: AuthUser, sub: string): string {
  return `mock-access-${sub}-${Date.now()}`;
}

function createRefreshToken(_info: AuthUser, sub: string): string {
  const token = `mock-refresh-${sub}-${Date.now()}`;
  const payload = { exp: Math.floor(Date.now() / 1000) + 86400 };
  mockDb.saveSession(token, { sub, username: '', email: '', password: '', role: 'employee', name: '', tenant_id: null }, payload.exp);
  return token;
}

export async function handleLogin(data: LoginRequest): Promise<LoginResponse> {
  const user = await run(() => mockDb.findUser(data.email, data.username));
  if (!user || user.password !== data.password) throw new Error(ERR_INVALID);
  const info = mockDb.toUserInfo(user);
  const access = createAccessToken(info, user.sub);
  const refresh = createRefreshToken(info, user.sub);
  return { accessToken: access, refreshToken: refresh, user: info };
}

export async function handleRegister(data: { orgCode: string; email: string; password: string; role: string }): Promise<LoginResponse> {
  const org = await run(() => mockDb.findOrg());
  if (!org) throw new Error(ERR_INVALID);
  if (await run(() => mockDb.findUserByEmailInOrg(data.orgCode, data.email))) throw new Error('Email already registered');
  const username = data.email.split('@')[0];
  const name = username.charAt(0).toUpperCase() + username.slice(1);
  const user = await run(() => mockDb.addUser(data.orgCode, { username, email: data.email, password: data.password, role: data.role as 'super_admin' | 'client_admin' | 'employee', name, tenant_id: null }));
  const info = mockDb.toUserInfo(user);
  const access = createAccessToken(info, user.sub);
  const refresh = createRefreshToken(info, user.sub);
  return { accessToken: access, refreshToken: refresh, user: info };
}

export async function handleRefresh(refreshToken: string | undefined): Promise<RefreshResponse> {
  const session = await run(() => mockDb.getSession(refreshToken));
  if (!session) throw new Error('Session expired');
  mockDb.revokeSession(refreshToken);
  const info = mockDb.toUserInfo(session.user);
  const access = createAccessToken(info, session.user.sub);
  const refresh = createRefreshToken(info, session.user.sub);
  return { accessToken: access, refreshToken: refresh };
}

export async function handleLogout(refreshToken: string | undefined): Promise<VerifyResponse> {
  mockDb.revokeSession(refreshToken);
  return { ok: true };
}

export async function handleVerify(_accessToken: string | undefined): Promise<VerifyResponse> { return { ok: true }; }

export async function handleGetTenants(): Promise<Tenant[]> { return mockDb.getTenants(); }

export async function handleCreateTenant(data: TenantCreateRequest): Promise<TenantCreateResponse> {
  const existing = await run(() => mockDb.getTenantByShortCode(data.short_code));
  if (existing) throw new Error('Tenant with this short code already exists');
  if (data.storage_quota_gb < 1) throw new Error('Storage quota must be at least 1 GB');
  return await run(() => mockDb.createTenant(data));
}

export async function handleUpdateTenant(id: string, data: TenantUpdateRequest): Promise<Tenant> {
  const tenant = await run(() => mockDb.updateTenant(id, data));
  if (!tenant) throw new Error('Tenant not found');
  return tenant;
}

export async function handleSuspendTenant(id: string): Promise<Tenant> {
  const tenant = await run(() => mockDb.suspendTenant(id));
  if (!tenant) throw new Error('Tenant not found');
  return tenant;
}

export async function handleReactivateTenant(id: string): Promise<Tenant> {
  const tenant = await run(() => mockDb.reactivateTenant(id));
  if (!tenant) throw new Error('Tenant not found');
  return tenant;
}

export async function handleGetTenantQuota(): Promise<QuotaResponse> {
  const tenants = mockDb.getTenants();
  const tenant = tenants.find(t => t.status === 'active') ?? tenants[0];
  return mockDb.getTenantQuota(tenant?.id ?? '') ?? { used_gb: 0, total_gb: 0 };
}

// Mock search data
const mockSearchResults: SearchResult[] = [
  {
    document_id: 'doc-1',
    chunk_index: 0,
    content: 'The company policy states that all employees must complete annual security training by March 31st.',
    score: 0.95,
    original_filename: 'security_policy.pdf',
  },
  {
    document_id: 'doc-2',
    chunk_index: 1,
    content: 'Annual leave policy: Employees are entitled to 25 days of paid leave per year, plus public holidays.',
    score: 0.88,
    original_filename: 'hr_policy.pdf',
  },
  {
    document_id: 'doc-3',
    chunk_index: 0,
    content: 'SOP for incident reporting: All security incidents must be reported within 24 hours via the incident portal.',
    score: 0.82,
    original_filename: 'incident_sop.pdf',
  },
];

export async function handleSearch(data: SearchRequest): Promise<SearchResponse> {
  await run(() => {});
  const query = data.query.toLowerCase();
  const filtered = mockSearchResults.filter(r => 
    r.content.toLowerCase().includes(query) || r.original_filename.toLowerCase().includes(query)
  );
  return {
    results: filtered.slice(0, data.top_k ?? 10),
    query: data.query,
    total_results: filtered.length,
  };
}

export async function handleSuggest(data: SuggestRequest): Promise<SuggestResponse> {
  await run(() => {});
  const query = data.query.toLowerCase();
  const suggestions = [
    'security policy',
    'annual leave policy',
    'incident reporting',
    'password reset',
    'data retention',
  ].filter(s => s.toLowerCase().includes(query)).slice(0, data.limit ?? 5);
  return { suggestions };
}

// Mock answers data
export async function handleAskQuestion(data: AnswerRequest): Promise<AnswerResponse> {
  await run(() => {});
  const question = data.question.toLowerCase();
  
  if (question.includes('security') || question.includes('training')) {
    return {
      question: data.question,
      answer_phrase: 'All employees must complete annual security training by March 31st.',
      routing: 'answered',
      confidence: 0.95,
      sources: [
        {
          document_id: 'doc-1',
          chunk_index: 0,
          original_filename: 'security_policy.pdf',
          score: 0.95,
          excerpt: 'The company policy states that all employees must complete annual security training by March 31st.',
        },
      ],
      followups: ['When is the deadline?', 'Where can I access the training?'],
      spellcheck: { applied: false, original: '', corrected: '', corrections: [] },
      source_document_id: 'doc-1',
      source_chunk_index: 0,
    };
  }
  
  if (question.includes('leave') || question.includes('holiday') || question.includes('vacation')) {
    return {
      question: data.question,
      answer_phrase: 'Employees are entitled to 25 days of paid leave per year, plus public holidays.',
      routing: 'answered',
      confidence: 0.92,
      sources: [
        {
          document_id: 'doc-2',
          chunk_index: 1,
          original_filename: 'hr_policy.pdf',
          score: 0.88,
          excerpt: 'Annual leave policy: Employees are entitled to 25 days of paid leave per year, plus public holidays.',
        },
      ],
      followups: ['How do I request leave?', 'Can I carry over unused leave?'],
      spellcheck: { applied: false, original: '', corrected: '', corrections: [] },
      source_document_id: 'doc-2',
      source_chunk_index: 1,
    };
  }
  
  if (question.includes('incident') || question.includes('report') || question.includes('security incident')) {
    return {
      question: data.question,
      answer_phrase: 'All security incidents must be reported within 24 hours via the incident portal.',
      routing: 'answered',
      confidence: 0.89,
      sources: [
        {
          document_id: 'doc-3',
          chunk_index: 0,
          original_filename: 'incident_sop.pdf',
          score: 0.82,
          excerpt: 'SOP for incident reporting: All security incidents must be reported within 24 hours via the incident portal.',
        },
      ],
      followups: ['What is the incident portal URL?', 'What details are required?'],
      spellcheck: { applied: false, original: '', corrected: '', corrections: [] },
      source_document_id: 'doc-3',
      source_chunk_index: 0,
    };
  }
  
  return {
    question: data.question,
    answer_phrase: '',
    routing: 'no_answer',
    confidence: 0,
    sources: [],
    followups: ['Try asking about security training', 'Ask about leave policy', 'Ask about incident reporting'],
    spellcheck: { applied: false, original: '', corrected: '', corrections: [] },
    source_document_id: null,
    source_chunk_index: null,
  };
}

// Mock feedback (VQ-305)
// Mirrors app/routes/feedback.py:
//   - validation errors -> 422 (pydantic runs before the handler)
//   - unknown answer on POST -> 404 "Answer not found"
//   - duplicate POST -> 409 (one vote per user per answer)
//   - PATCH/GET on missing feedback -> 404 "Feedback not found"
// The mock models a single signed-in user, so one vote per answer id.
const mockAnswerIds = new Set<string>();
const mockFeedbackByAnswer = new Map<string, FeedbackResponse>();
let mockFeedbackSeq = 0;

export function registerMockAnswer(answerId: string): void {
  mockAnswerIds.add(answerId);
}

export function resetMockFeedback(): void {
  mockAnswerIds.clear();
  mockFeedbackByAnswer.clear();
  mockFeedbackSeq = 0;
}

function assertVote(vote: number): void {
  if (vote !== 1 && vote !== -1) {
    throw new ApiError('vote must be 1 (thumbs up) or -1 (thumbs down)', 422);
  }
}

function assertComment(comment: string | null | undefined): void {
  if (comment != null && comment.length > 500) {
    throw new ApiError('Comment must be 500 characters or fewer', 422);
  }
}

export async function handleGetFeedback(answerId: string): Promise<FeedbackResponse> {
  await latency();
  const existing = mockFeedbackByAnswer.get(answerId);
  if (!existing) throw new ApiError('Feedback not found', 404);
  return existing;
}

export async function handleCreateFeedback(
  answerId: string,
  body: FeedbackCreate,
): Promise<FeedbackResponse> {
  await latency();
  assertVote(body.vote);
  assertComment(body.comment);
  if (!mockAnswerIds.has(answerId)) throw new ApiError('Answer not found', 404);
  if (mockFeedbackByAnswer.has(answerId)) {
    throw new ApiError(
      'Feedback already exists for this answer from this user. Use PATCH to update.',
      409,
    );
  }
  const now = new Date().toISOString();
  const feedback: FeedbackResponse = {
    id: `mock-fb-${++mockFeedbackSeq}`,
    answer_id: answerId,
    user_id: 'mock-user',
    vote: body.vote,
    comment: body.comment ?? null,
    created_at: now,
    updated_at: now,
  };
  mockFeedbackByAnswer.set(answerId, feedback);
  return feedback;
}

export async function handleUpdateFeedback(
  answerId: string,
  body: FeedbackUpdate,
): Promise<FeedbackResponse> {
  await latency();
  if (body.vote !== undefined && body.vote !== null) assertVote(body.vote);
  assertComment(body.comment);
  const existing = mockFeedbackByAnswer.get(answerId);
  if (!existing) throw new ApiError('Feedback not found', 404);
  const updated: FeedbackResponse = {
    ...existing,
    vote: body.vote !== undefined && body.vote !== null ? body.vote : existing.vote,
    comment: body.comment !== undefined ? body.comment : existing.comment,
    updated_at: new Date().toISOString(),
  };
  mockFeedbackByAnswer.set(answerId, updated);
  return updated;
}

export async function handleListFeedback(params?: {
  page?: number;
  page_size?: number;
  answer_id?: string;
  vote?: 1 | -1;
}): Promise<FeedbackListResponse> {
  await latency();
  const page = params?.page ?? 1;
  const pageSize = params?.page_size ?? 20;
  let rows = Array.from(mockFeedbackByAnswer.values());
  if (params?.answer_id) rows = rows.filter((f) => f.answer_id === params.answer_id);
  if (params?.vote !== undefined) rows = rows.filter((f) => f.vote === params.vote);
  const total = rows.length;
  const start = (page - 1) * pageSize;
  return { feedback: rows.slice(start, start + pageSize), total, page, page_size: pageSize };
}