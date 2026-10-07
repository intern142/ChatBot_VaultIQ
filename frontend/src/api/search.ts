import { request } from './client';
import type {
  SearchRequest,
  SearchResponse,
  SuggestRequest,
  SuggestResponse,
} from './types';

export const search = (body: SearchRequest) =>
  request<SearchResponse>('/search', {
    method: 'POST',
    body: JSON.stringify(body),
  });

export const suggest = (params: SuggestRequest) => {
  const queryParams: Record<string, string | number | boolean> = { q: params.query };
  if (params.limit !== undefined) queryParams.limit = params.limit;
  return request<SuggestResponse>('/search/suggest', {
    params: queryParams,
  });
};