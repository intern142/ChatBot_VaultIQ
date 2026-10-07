import { request } from './client';
import type {
  AnswerRequest,
  AnswerResponse,
} from './types';

export const askQuestion = (body: AnswerRequest) =>
  request<AnswerResponse>('/answers', {
    method: 'POST',
    body: JSON.stringify(body),
  });