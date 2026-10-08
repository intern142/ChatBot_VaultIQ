import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useFeedback, FEEDBACK_ANSWER_ID_GAP } from '@/hooks/useFeedback';
import { createFeedback, updateFeedback, getFeedback } from '@/api/feedback';
import { ApiError } from '@/api/errors';
import type { FeedbackResponse } from '@/api/types';

vi.mock('@/api/feedback', () => ({
  createFeedback: vi.fn(),
  updateFeedback: vi.fn(),
  getFeedback: vi.fn(),
  listFeedback: vi.fn(),
}));

const mockedCreate = vi.mocked(createFeedback);
const mockedUpdate = vi.mocked(updateFeedback);
const mockedGet = vi.mocked(getFeedback);

const existingFeedback: FeedbackResponse = {
  id: 'fb-1',
  answer_id: 'ans-1',
  user_id: 'user-1',
  vote: 1,
  comment: 'Clear answer',
  created_at: '2026-10-08T10:00:00Z',
  updated_at: '2026-10-08T10:00:00Z',
};

describe('useFeedback', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockedGet.mockRejectedValue(new ApiError('Feedback not found', 404));
  });

  it('blocks submission without an answer id and reports the contract gap', async () => {
    const { result } = renderHook(() => useFeedback(null));
    let ok = true;
    await act(async () => {
      ok = await result.current.submit(1, 'good');
    });
    expect(ok).toBe(false);
    expect(result.current.error).toBe(FEEDBACK_ANSWER_ID_GAP);
    expect(result.current.success).toBe(false);
    expect(mockedCreate).not.toHaveBeenCalled();
    expect(mockedUpdate).not.toHaveBeenCalled();
  });

  it('requires a vote before submitting', async () => {
    const { result } = renderHook(() => useFeedback('ans-1'));
    await waitFor(() => expect(result.current.loading).toBe(false));
    let ok = true;
    await act(async () => {
      ok = await result.current.submit(null, null);
    });
    expect(ok).toBe(false);
    expect(result.current.error).toMatch(/thumbs up or thumbs down/i);
    expect(mockedCreate).not.toHaveBeenCalled();
  });

  it('rejects comments longer than 500 characters', async () => {
    const { result } = renderHook(() => useFeedback('ans-1'));
    await waitFor(() => expect(result.current.loading).toBe(false));
    let ok = true;
    await act(async () => {
      ok = await result.current.submit(1, 'x'.repeat(501));
    });
    expect(ok).toBe(false);
    expect(result.current.error).toMatch(/500 characters/i);
    expect(mockedCreate).not.toHaveBeenCalled();
  });

  it('submits new feedback, trims the comment, and shows success', async () => {
    mockedCreate.mockResolvedValue(existingFeedback);
    const { result } = renderHook(() => useFeedback('ans-1'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    let ok = false;
    await act(async () => {
      ok = await result.current.submit(1, '  Clear answer  ');
    });

    expect(ok).toBe(true);
    expect(result.current.success).toBe(true);
    expect(result.current.error).toBeNull();
    expect(result.current.existing).toEqual(existingFeedback);
    expect(mockedCreate).toHaveBeenCalledWith('ans-1', { vote: 1, comment: 'Clear answer' });
    expect(mockedUpdate).not.toHaveBeenCalled();
  });

  it('updates existing feedback via PATCH instead of creating a duplicate', async () => {
    mockedGet.mockResolvedValue(existingFeedback);
    const updated: FeedbackResponse = {
      ...existingFeedback,
      vote: -1,
      comment: null,
      updated_at: '2026-10-08T11:00:00Z',
    };
    mockedUpdate.mockResolvedValue(updated);

    const { result } = renderHook(() => useFeedback('ans-1'));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.existing).toEqual(existingFeedback);

    let ok = false;
    await act(async () => {
      ok = await result.current.submit(-1, null);
    });

    expect(ok).toBe(true);
    expect(result.current.success).toBe(true);
    expect(result.current.existing).toEqual(updated);
    expect(mockedUpdate).toHaveBeenCalledWith('ans-1', { vote: -1, comment: null });
    expect(mockedCreate).not.toHaveBeenCalled();
  });

  it('switches to PATCH when the backend reports a duplicate vote (409)', async () => {
    mockedCreate.mockRejectedValue(
      new ApiError('Feedback already exists for this answer from this user. Use PATCH to update.', 409),
    );
    mockedUpdate.mockResolvedValue(existingFeedback);

    const { result } = renderHook(() => useFeedback('ans-1'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    let ok = false;
    await act(async () => {
      ok = await result.current.submit(1, 'Clear answer');
    });

    expect(ok).toBe(true);
    expect(result.current.success).toBe(true);
    expect(result.current.error).toBeNull();
    expect(mockedUpdate).toHaveBeenCalledWith('ans-1', { vote: 1, comment: 'Clear answer' });
  });

  it('maps 401 to a session-expired message', async () => {
    mockedCreate.mockRejectedValue(new ApiError('Session expired', 401));
    const { result } = renderHook(() => useFeedback('ans-1'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.submit(1, null);
    });

    expect(result.current.success).toBe(false);
    expect(result.current.error).toBe('Your session has expired. Please sign in again.');
  });

  it('maps 403 to a permission message', async () => {
    mockedCreate.mockRejectedValue(new ApiError('Not enough permissions', 403));
    const { result } = renderHook(() => useFeedback('ans-1'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.submit(1, null);
    });

    expect(result.current.success).toBe(false);
    expect(result.current.error).toBe('You do not have permission to give feedback on this answer.');
  });

  it('surfaces other backend errors as-is', async () => {
    mockedCreate.mockRejectedValue(new ApiError('Answer not found', 404));
    const { result } = renderHook(() => useFeedback('ans-1'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.submit(1, null);
    });

    expect(result.current.error).toBe('Answer not found');
  });

  it('reports loading while existing feedback is fetched', () => {
    mockedGet.mockReturnValue(new Promise<FeedbackResponse>(() => {}));
    const { result } = renderHook(() => useFeedback('ans-1'));
    expect(result.current.loading).toBe(true);
    expect(result.current.existing).toBeNull();
  });

  it('treats a 404 on fetch as "no feedback yet", not an error', async () => {
    const { result } = renderHook(() => useFeedback('ans-1'));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.existing).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('maps a 401 on fetch to a session-expired message', async () => {
    mockedGet.mockRejectedValue(new ApiError('Session expired', 401));
    const { result } = renderHook(() => useFeedback('ans-1'));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.existing).toBeNull();
    expect(result.current.error).toBe('Your session has expired. Please sign in again.');
  });

  it('edit() clears the success state so feedback can be changed', async () => {
    mockedCreate.mockResolvedValue(existingFeedback);
    const { result } = renderHook(() => useFeedback('ans-1'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.submit(1, 'Clear answer');
    });
    expect(result.current.success).toBe(true);

    act(() => {
      result.current.edit();
    });
    expect(result.current.success).toBe(false);
    expect(result.current.existing).toEqual(existingFeedback);
  });
});
