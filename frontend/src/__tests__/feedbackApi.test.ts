import { describe, it, expect, beforeEach } from 'vitest';
import { createFeedback, updateFeedback, getFeedback, listFeedback } from '@/api/feedback';
import { registerMockAnswer, resetMockFeedback } from '@/api/mock/handlers';
import { ApiError } from '@/api/errors';
import type { FeedbackCreate, FeedbackResponse } from '@/api/types';

async function catchError(p: Promise<unknown>): Promise<unknown> {
  try {
    await p;
    return null;
  } catch (err) {
    return err;
  }
}

function expectApiError(err: unknown, status: number): void {
  expect(err).toBeInstanceOf(ApiError);
  expect((err as ApiError).status).toBe(status);
}

describe('feedback API (mock mode)', () => {
  beforeEach(() => {
    resetMockFeedback();
  });

  it('creates feedback with a vote and comment', async () => {
    registerMockAnswer('ans-1');
    const created = await createFeedback('ans-1', { vote: 1, comment: 'Clear answer' });
    expect(created).toMatchObject({
      answer_id: 'ans-1',
      vote: 1,
      comment: 'Clear answer',
    });
    expect(created.id).toBeTruthy();
    expect(created.user_id).toBeTruthy();
    expect(created.created_at).toBeTruthy();
    expect(created.updated_at).toBeTruthy();
  });

  it('creates feedback without a comment', async () => {
    registerMockAnswer('ans-1');
    const created = await createFeedback('ans-1', { vote: -1 });
    expect(created.vote).toBe(-1);
    expect(created.comment).toBeNull();
  });

  it('rejects a duplicate vote with 409', async () => {
    registerMockAnswer('ans-1');
    await createFeedback('ans-1', { vote: 1 });
    const err = await catchError(createFeedback('ans-1', { vote: -1 }));
    expectApiError(err, 409);
    expect((err as ApiError).message).toContain('already exists');
  });

  it('updates an existing vote via PATCH', async () => {
    registerMockAnswer('ans-1');
    await createFeedback('ans-1', { vote: 1, comment: 'nice' });
    const updated = await updateFeedback('ans-1', { vote: -1, comment: null });
    expect(updated.vote).toBe(-1);
    expect(updated.comment).toBeNull();
    const fetched = await getFeedback('ans-1');
    expect(fetched.vote).toBe(-1);
  });

  it('returns 404 for feedback on an unknown answer', async () => {
    const err = await catchError(createFeedback('missing-answer', { vote: 1 }));
    expectApiError(err, 404);
    expect((err as ApiError).message).toBe('Answer not found');
  });

  it('returns 404 when fetching feedback that does not exist', async () => {
    registerMockAnswer('ans-1');
    const err = await catchError(getFeedback('ans-1'));
    expectApiError(err, 404);
    expect((err as ApiError).message).toBe('Feedback not found');
  });

  it('validates comment length with 422', async () => {
    registerMockAnswer('ans-1');
    const err = await catchError(createFeedback('ans-1', { vote: 1, comment: 'x'.repeat(501) }));
    expectApiError(err, 422);
  });

  it('validates vote values with 422', async () => {
    registerMockAnswer('ans-1');
    const badBody = { vote: 7, comment: null } as unknown as FeedbackCreate;
    const err = await catchError(createFeedback('ans-1', badBody));
    expectApiError(err, 422);
  });

  it('lists feedback with answer/vote filters and pagination', async () => {
    registerMockAnswer('ans-1');
    registerMockAnswer('ans-2');
    const first = await createFeedback('ans-1', { vote: 1, comment: 'good' });
    const second = await createFeedback('ans-2', { vote: -1, comment: 'unclear' });

    const all = await listFeedback();
    expect(all.total).toBe(2);
    expect(all.page).toBe(1);
    expect(all.page_size).toBe(20);

    const byAnswer = await listFeedback({ answer_id: 'ans-1' });
    expect(byAnswer.total).toBe(1);
    expect(byAnswer.feedback[0].id).toBe(first.id);

    const byVote = await listFeedback({ vote: -1 });
    expect(byVote.total).toBe(1);
    expect(byVote.feedback[0].id).toBe(second.id);

    const page2 = await listFeedback({ page_size: 1, page: 2 });
    expect(page2.total).toBe(2);
    expect(page2.feedback).toHaveLength(1);
    expect(page2.feedback[0].id).toBe(second.id);
  });

  it('keeps feedback for different answers independent', async () => {
    registerMockAnswer('ans-1');
    registerMockAnswer('ans-2');
    const a = await createFeedback('ans-1', { vote: 1 });
    const b = await createFeedback('ans-2', { vote: -1 });
    expect(a.id).not.toBe(b.id);
    expect(a.answer_id).not.toBe(b.answer_id);
    const fetchedA: FeedbackResponse = await getFeedback('ans-1');
    const fetchedB: FeedbackResponse = await getFeedback('ans-2');
    expect(fetchedA.vote).toBe(1);
    expect(fetchedB.vote).toBe(-1);
    await updateFeedback('ans-2', { vote: 1 });
    const updatedB: FeedbackResponse = await getFeedback('ans-2');
    expect(updatedB.vote).toBe(1);
    expect(updatedB.answer_id).toBe('ans-2');
    const stillA: FeedbackResponse = await getFeedback('ans-1');
    expect(stillA.vote).toBe(1);
    expect(stillA.id).toBe(a.id);
  });
});
