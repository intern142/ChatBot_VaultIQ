import { request } from './client';
import type {
  FeedbackCreate,
  FeedbackUpdate,
  FeedbackResponse,
  FeedbackListResponse,
} from './types';

export const createFeedback = (answerId: string, body: FeedbackCreate) =>
  request<FeedbackResponse>(`/answers/${answerId}/feedback`, {
    method: 'POST',
    body: JSON.stringify(body),
  });

export const updateFeedback = (answerId: string, body: FeedbackUpdate) =>
  request<FeedbackResponse>(`/answers/${answerId}/feedback`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });

export const getFeedback = (answerId: string) =>
  request<FeedbackResponse>(`/answers/${answerId}/feedback`);

export const listFeedback = (params?: {
  page?: number;
  page_size?: number;
  answer_id?: string;
  vote?: 1 | -1;
}) =>
  request<FeedbackListResponse>('/answers/feedback', {
    params: params as Record<string, string | number | boolean> | undefined,
  });