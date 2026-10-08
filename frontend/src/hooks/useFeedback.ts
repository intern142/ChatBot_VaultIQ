import { useCallback, useEffect, useState } from 'react';
import { createFeedback, getFeedback, updateFeedback } from '@/api/feedback';
import { ApiError } from '@/api/errors';
import type { FeedbackResponse } from '@/api/types';

export type FeedbackVote = 1 | -1;

export const FEEDBACK_ANSWER_ID_GAP =
  'Feedback could not be submitted: the answer service did not return an answer id, so there is no answer to attach the feedback to. This backend contract gap is tracked in FRESH.md Phase 7.';

const COMMENT_MAX_LENGTH = 500;

function toMessage(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return 'Your session has expired. Please sign in again.';
    if (err.status === 403) return 'You do not have permission to give feedback on this answer.';
    if (err.message) return err.message;
    return 'Feedback request failed.';
  }
  if (err instanceof Error && err.message) return err.message;
  return 'Feedback request failed.';
}

export interface UseFeedbackResult {
  existing: FeedbackResponse | null;
  loading: boolean;
  submitting: boolean;
  error: string | null;
  success: boolean;
  submit: (vote: FeedbackVote | null, comment: string | null) => Promise<boolean>;
  edit: () => void;
  dismissError: () => void;
}

export function useFeedback(answerId: string | null): UseFeedbackResult {
  const [existing, setExisting] = useState<FeedbackResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setExisting(null);
    setError(null);
    setSuccess(false);

    if (!answerId) {
      setLoading(false);
      return;
    }

    setLoading(true);
    getFeedback(answerId)
      .then((feedback) => {
        if (!cancelled) setExisting(feedback);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        // 404 = the user has not given feedback on this answer yet (or the
        // answer is gone/another tenant's — the backend deliberately does
        // not distinguish, so there is nothing to leak here).
        if (err instanceof ApiError && err.status === 404) return;
        setError(toMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [answerId]);

  const submit = useCallback(
    async (vote: FeedbackVote | null, comment: string | null): Promise<boolean> => {
      if (vote !== 1 && vote !== -1) {
        setError('Choose thumbs up or thumbs down before submitting.');
        return false;
      }

      const trimmed = comment?.trim() ?? null;
      if (trimmed && trimmed.length > COMMENT_MAX_LENGTH) {
        setError(`Comments must be ${COMMENT_MAX_LENGTH} characters or fewer.`);
        return false;
      }

      if (!answerId) {
        setError(FEEDBACK_ANSWER_ID_GAP);
        return false;
      }

      setSubmitting(true);
      setError(null);
      setSuccess(false);
      try {
        const body = { vote, comment: trimmed };
        let saved: FeedbackResponse;
        if (existing) {
          saved = await updateFeedback(answerId, body);
        } else {
          try {
            saved = await createFeedback(answerId, body);
          } catch (err) {
            // 409 = a vote already exists (e.g. a stale "no feedback yet"
            // state). The backend contract says to switch to PATCH instead
            // of submitting a duplicate.
            if (err instanceof ApiError && err.status === 409) {
              saved = await updateFeedback(answerId, body);
            } else {
              throw err;
            }
          }
        }
        setExisting(saved);
        setSuccess(true);
        return true;
      } catch (err) {
        setError(toMessage(err));
        return false;
      } finally {
        setSubmitting(false);
      }
    },
    [answerId, existing],
  );

  const edit = useCallback(() => {
    setSuccess(false);
    setError(null);
  }, []);

  const dismissError = useCallback(() => {
    setError(null);
  }, []);

  return { existing, loading, submitting, error, success, submit, edit, dismissError };
}
