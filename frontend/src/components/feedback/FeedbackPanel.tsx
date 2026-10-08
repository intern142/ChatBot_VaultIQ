import { useEffect, useState } from 'react';
import { useFeedback, type FeedbackVote } from '@/hooks/useFeedback';
import { Button } from '@/components/ui/Button';
import { Alert } from '@/components/ui/Alert';
import { Spinner } from '@/components/ui/Spinner';

interface FeedbackPanelProps {
  answerId: string | null;
}

export function FeedbackPanel({ answerId }: FeedbackPanelProps) {
  const { existing, loading, submitting, error, success, submit, edit, dismissError } =
    useFeedback(answerId);
  const [vote, setVote] = useState<FeedbackVote | null>(null);
  const [comment, setComment] = useState('');

  useEffect(() => {
    if (existing) {
      setVote(existing.vote);
      setComment(existing.comment ?? '');
    } else {
      setVote(null);
      setComment('');
    }
  }, [existing]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await submit(vote, comment);
  };

  return (
    <div style={styles.panel}>
      <p style={styles.title}>Was this helpful?</p>

      {loading ? (
        <div style={styles.loading}>
          <Spinner size="sm" label="Loading feedback" />
          <span>Loading feedback…</span>
        </div>
      ) : (
        <>
          {success && existing ? (
            <div style={styles.successBlock}>
              <Alert variant="success">
                Feedback submitted — thanks! You voted {existing.vote === 1 ? '👍' : '👎'}.
                {existing.comment ? ` Comment: “${existing.comment}”` : ''}
              </Alert>
              <Button variant="outline" size="sm" onClick={edit} style={styles.editButton}>
                Update feedback
              </Button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} style={styles.form}>
              <div style={styles.voteRow}>
                <button
                  type="button"
                  aria-label="Thumbs up"
                  aria-pressed={vote === 1}
                  onClick={() => setVote(1)}
                  disabled={submitting}
                  style={{ ...styles.voteButton, ...(vote === 1 ? styles.voteButtonActive : {}) }}
                >
                  👍
                </button>
                <button
                  type="button"
                  aria-label="Thumbs down"
                  aria-pressed={vote === -1}
                  onClick={() => setVote(-1)}
                  disabled={submitting}
                  style={{ ...styles.voteButton, ...(vote === -1 ? styles.voteButtonDownActive : {}) }}
                >
                  👎
                </button>
                <span style={styles.voteHint}>
                  {vote === null ? 'Select a vote' : vote === 1 ? 'Helpful' : 'Not helpful'}
                </span>
              </div>

              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                maxLength={500}
                rows={2}
                placeholder="Add a comment (optional, max 500 characters)"
                aria-label="Feedback comment"
                disabled={submitting}
                style={styles.comment}
              />

              <div style={styles.footer}>
                <span style={styles.counter}>{comment.length}/500</span>
                <Button
                  type="submit"
                  size="sm"
                  loading={submitting}
                  disabled={loading}
                  style={styles.submitButton}
                >
                  {existing ? 'Update feedback' : 'Submit feedback'}
                </Button>
              </div>
            </form>
          )}

          {error && (
            <Alert variant="error" onDismiss={dismissError} style={styles.error}>
              {error}
            </Alert>
          )}
        </>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  panel: {
    marginTop: '16px',
    paddingTop: '16px',
    borderTop: '1px solid #e2e8f0',
  },
  title: { margin: '0 0 12px', fontSize: '13px', fontWeight: 600, color: '#334155' },
  loading: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: '13px',
    color: '#64748b',
  },
  form: { display: 'flex', flexDirection: 'column', gap: '10px' },
  voteRow: { display: 'flex', alignItems: 'center', gap: '8px' },
  voteButton: {
    width: '40px',
    height: '40px',
    fontSize: '18px',
    background: '#f8fafc',
    border: '1px solid #cbd5e1',
    borderRadius: '8px',
    cursor: 'pointer',
    transition: 'all 0.15s',
    lineHeight: 1,
  },
  voteButtonActive: {
    background: '#dcfce7',
    border: '1px solid #16a34a',
    boxShadow: '0 0 0 2px #bbf7d0',
  },
  voteButtonDownActive: {
    background: '#fee2e2',
    border: '1px solid #dc2626',
    boxShadow: '0 0 0 2px #fecaca',
  },
  voteHint: { fontSize: '13px', color: '#64748b' },
  comment: {
    padding: '8px 12px',
    border: '1px solid #cbd5e1',
    borderRadius: '8px',
    fontSize: '13px',
    fontFamily: 'inherit',
    outline: 'none',
    resize: 'vertical',
    minHeight: '52px',
    transition: 'border-color 0.15s, box-shadow 0.15s',
  },
  footer: { display: 'flex', alignItems: 'center', justifyContent: 'space-between' },
  counter: { fontSize: '12px', color: '#94a3b8' },
  submitButton: { minWidth: '140px' },
  successBlock: { display: 'flex', flexDirection: 'column', gap: '10px', alignItems: 'flex-start' },
  editButton: { alignSelf: 'flex-start' },
  error: { marginTop: '10px' },
};
