import { request } from './client';
import type { InviteAcceptResponse } from './types';

export const acceptInvite = (code: string, password: string) =>
  request<InviteAcceptResponse>('/invite/accept', {
    method: 'POST',
    body: JSON.stringify({ code, password }),
    skipAuth: true,
    skipRefreshOn401: true,
  });