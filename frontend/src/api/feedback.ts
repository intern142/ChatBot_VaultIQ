import { request } from './client';
import { isMockMode } from './config';
import type {
  FeedbackCreate,
  FeedbackUpdate,
  FeedbackResponse,
  FeedbackListResponse,
} from './types';

export const createFeedback = async (
  answerId: string,
  body: FeedbackCreate,
): Promise<FeedbackResponse> => {
  if (isMockMode()) {
    const { handleCreateFeedback } = await import('./mock/handlers');
    return handleCreateFeedback(answerId, body);
  }
  return request<FeedbackResponse>(`/answers/${answerId}/feedback`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
};

export const updateFeedback = async (
  answerId: string,
  body: FeedbackUpdate,
): Promise<FeedbackResponse> => {
  if (isMockMode()) {
    const { handleUpdateFeedback } = await import('./mock/handlers');
    return handleUpdateFeedback(answerId, body);
  }
  return request<FeedbackResponse>(`/answers/${answerId}/feedback`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
};

export const getFeedback = async (answerId: string): Promise<FeedbackResponse> => {
  if (isMockMode()) {
    const { handleGetFeedback } = await import('./mock/handlers');
    return handleGetFeedback(answerId);
  }
  return request<FeedbackResponse>(`/answers/${answerId}/feedback`);
};

export const listFeedback = async (params?: {
  page?: number;
  page_size?: number;
  answer_id?: string;
  vote?: 1 | -1;
}): Promise<FeedbackListResponse> => {
  if (isMockMode()) {
    const { handleListFeedback } = await import('./mock/handlers');
    return handleListFeedback(params);
  }
  return request<FeedbackListResponse>('/answers/feedback', {
    params: params as Record<string, string | number | boolean> | undefined,
  });
};
