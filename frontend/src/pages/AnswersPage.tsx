import { useAuth } from '@/context/AuthContext';
import { useAnswers } from '@/hooks/useAnswers';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { EmptyState } from '@/components/ui/EmptyState';
import { FeedbackPanel } from '@/components/feedback';
import type { AnswerResponse, AnswerSource } from '@/api/types';

export default function AnswersPage() {
  const { role } = useAuth();
  const {
    question,
    setQuestion,
    answer,
    loading,
    error,
    ask,
    clearAnswer,
  } = useAnswers();

  const isClientAdminOrEmployee = role === 'client_admin' || role === 'employee';
  const isSuperAdmin = role === 'super_admin';

  if (isSuperAdmin) {
    return (
      <div style={styles.container}>
        <div style={styles.accessDenied}>
          <h2>Access Denied</h2>
          <p>Super Admin cannot access tenant answers. This feature is for tenant users only.</p>
        </div>
      </div>
    );
  }

  if (!isClientAdminOrEmployee) {
    return (
      <div style={styles.container}>
        <div style={styles.accessDenied}>
          <h2>Access Denied</h2>
          <p>You don't have permission to access answers.</p>
        </div>
      </div>
    );
  }

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (question.trim()) {
      ask(question);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>Ask a Question</h1>
        <p style={styles.subtitle}>Get answers from your organization's documents</p>
      </div>

      <form onSubmit={handleSubmit} style={styles.form}>
        <div style={styles.inputWrapper}>
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question about your documents..."
            style={styles.textarea}
            disabled={loading}
            rows={3}
            autoFocus
          />
          <Button
            type="submit"
            loading={loading}
            disabled={!question.trim() || loading}
            style={styles.askButton}
          >
            {loading ? <><Spinner size="sm" /> Asking…</> : 'Ask'}
          </Button>
        </div>

        {error && <Alert variant="error" onDismiss={() => setQuestion('')}>{error}</Alert>}

        <div style={styles.hint}>
          <span>Try asking:</span>
          <span style={styles.example}>"What is the security training deadline?"</span>
          <span style={styles.example}>"How many days of leave do I get?"</span>
          <span style={styles.example}>"How do I report a security incident?"</span>
        </div>
      </form>

      <div style={styles.answerSection}>
        {loading ? (
          <div style={styles.loading}>
            <Spinner size="lg" />
            <span>Searching for an answer...</span>
          </div>
        ) : answer ? (
          <AnswerCard answer={answer} onClear={clearAnswer} />
        ) : question.trim() ? (
          <EmptyState
            icon="🤔"
            title="No answer found"
            description="The documents don't contain an answer to this question"
            action={{ label: 'Clear', onClick: clearAnswer }}
          />
        ) : (
          <EmptyState
            icon="❓"
            title="Ask a question"
            description="Type a question above to get an answer from your documents"
          />
        )}
      </div>
    </div>
  );
}

interface AnswerCardProps {
  answer: AnswerResponse;
  onClear: () => void;
}

function AnswerCard({ answer, onClear }: AnswerCardProps) {
  const routingColors: Record<string, { bg: string; color: string; label: string }> = {
    answered: { bg: '#dcfce7', color: '#166534', label: 'Answered' },
    no_answer: { bg: '#fef3c7', color: '#92400e', label: 'No Answer' },
    partial: { bg: '#dbeafe', color: '#1e40af', label: 'Partial' },
  };

  const routingConfig = routingColors[answer.routing] || { bg: '#f3f4f6', color: '#6b7280', label: answer.routing };

  return (
    <div style={styles.answerCard}>
      <div style={styles.answerHeader}>
        <div style={styles.answerMeta}>
          <span style={styles.questionLabel}>Question:</span>
          <p style={styles.questionText}>{answer.question}</p>
        </div>
        <div style={styles.answerActions}>
          <span
            style={{
              ...styles.routingBadge,
              backgroundColor: routingConfig.bg,
              color: routingConfig.color,
            }}
          >
            {routingConfig.label}
          </span>
          {answer.confidence > 0 && (
            <span style={styles.confidence}>
              Confidence: {(answer.confidence * 100).toFixed(0)}%
            </span>
          )}
          <Button variant="ghost" size="sm" onClick={onClear}>
            Clear
          </Button>
        </div>
      </div>

      {answer.answer_phrase && (
        <div style={styles.answerPhrase}>
          <p style={styles.phraseLabel}>Answer:</p>
          <p style={styles.phraseText}>{answer.answer_phrase}</p>
        </div>
      )}

      {/* answerId is null because POST /answers returns no answer id — the
          backend never persists an Answer row for the live ask flow, so there
          is nothing to attach feedback to. The panel degrades honestly and the
          gap is documented in FRESH.md Phase 7. */}
      <FeedbackPanel answerId={null} />

      {answer.sources && answer.sources.length > 0 && (
        <div style={styles.sourcesSection}>
          <h4 style={styles.sourcesTitle}>Sources</h4>
          <div style={styles.sourcesList}>
            {answer.sources.map((source, index) => (
              <SourceCard key={`${source.document_id}-${source.chunk_index}-${index}`} source={source} />
            ))}
          </div>
        </div>
      )}

      {answer.followups && answer.followups.length > 0 && (
        <div style={styles.followupsSection}>
          <p style={styles.followupsTitle}>Suggested follow-ups:</p>
          <div style={styles.followupsList}>
            {answer.followups.map((followup, index) => (
              <button
                key={index}
                style={styles.followupButton}
                onClick={() => { /* Would need to trigger new question */ }}
              >
                {followup}
              </button>
            ))}
          </div>
        </div>
      )}

      {answer.spellcheck?.applied && (
        <div style={styles.spellcheck}>
          <span>Did you mean: </span>
          <strong>{answer.spellcheck.corrected}</strong>
        </div>
      )}
    </div>
  );
}

interface SourceCardProps {
  source: AnswerSource;
}

function SourceCard({ source }: SourceCardProps) {
  return (
    <div style={styles.sourceCard}>
      <div style={styles.sourceHeader}>
        <span style={styles.sourceFilename}>{source.original_filename}</span>
        <span style={styles.sourceScore}>Score: {(source.score * 100).toFixed(1)}%</span>
      </div>
      <p style={styles.sourceExcerpt}>{source.excerpt}</p>
      <div style={styles.sourceMeta}>
        <span>Doc: {source.document_id.slice(0, 8)}...</span>
        <span>Chunk: {source.chunk_index}</span>
      </div>
    </div>
  );
}

interface AnswerCardProps {
  answer: AnswerResponse;
  onClear: () => void;
}

const styles: Record<string, React.CSSProperties> = {
  container: { padding: '24px', maxWidth: '900px', margin: '0 auto' },
  header: { marginBottom: '24px' },
  title: { margin: '0 0 8px', fontSize: '24px', fontWeight: 700, color: '#0f172a' },
  subtitle: { margin: '0 0 24px', color: '#64748b', textAlign: 'center', fontSize: '14px' },
  form: { marginBottom: '24px' },
  inputWrapper: { display: 'flex', gap: '12px', alignItems: 'flex-start' },
  textarea: {
    flex: 1,
    padding: '12px 16px',
    border: '1px solid #cbd5e1',
    borderRadius: '8px',
    fontSize: '16px',
    fontFamily: 'inherit',
    outline: 'none',
    resize: 'vertical',
    minHeight: '100px',
    transition: 'border-color 0.15s, box-shadow 0.15s',
  },
  askButton: { height: '100px', padding: '0 24px', alignSelf: 'flex-start' },
  hint: { display: 'flex', flexWrap: 'wrap', gap: '12px', marginTop: '16px', color: '#64748b', fontSize: '13px' },
  example: { background: '#f1f5f9', padding: '4px 10px', borderRadius: '4px', fontFamily: 'monospace', fontSize: '12px', cursor: 'pointer' },
  answerSection: { marginTop: '24px' },
  loading: { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px', padding: '48px', color: '#64748b' },
  answerCard: {
    padding: '24px',
    background: 'white',
    border: '1px solid #e2e8f0',
    borderRadius: '12px',
    boxShadow: '0 1px 3px 0 rgb(0 0 0 / 0.1)',
  },
  answerHeader: { display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' },
  answerMeta: { flex: 1 },
  questionLabel: { fontSize: '12px', fontWeight: 600, color: '#64748b', marginBottom: '4px' },
  questionText: { margin: 0, fontSize: '16px', color: '#0f172a', lineHeight: '1.5' },
  answerActions: { display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' },
  routingBadge: { fontSize: '12px', fontWeight: 600, padding: '4px 10px', borderRadius: '6px' },
  confidence: { fontSize: '13px', color: '#64748b', background: '#f1f5f9', padding: '4px 10px', borderRadius: '6px' },
  answerPhrase: { marginTop: '16px', paddingTop: '16px', borderTop: '1px solid #e2e8f0' },
  phraseLabel: { fontSize: '13px', fontWeight: 600, color: '#64748b', marginBottom: '8px' },
  phraseText: { margin: 0, fontSize: '16px', color: '#0f172a', lineHeight: '1.6' },
  sourcesSection: { marginTop: '24px', paddingTop: '16px', borderTop: '1px solid #e2e8f0' },
  sourcesTitle: { margin: '0 0 12px', fontSize: '14px', fontWeight: 600, color: '#0f172a' },
  sourcesList: { display: 'flex', flexDirection: 'column', gap: '12px' },
  sourceCard: {
    padding: '16px',
    background: '#f8fafc',
    border: '1px solid #e2e8f0',
    borderRadius: '8px',
  },
  sourceHeader: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' },
  sourceFilename: { fontSize: '13px', fontWeight: 500, color: '#0f172a' },
  sourceScore: { fontSize: '12px', color: '#64748b', background: '#f1f5f9', padding: '2px 8px', borderRadius: '4px' },
  sourceExcerpt: { margin: '8px 0', fontSize: '13px', color: '#334155', lineHeight: '1.5' },
  sourceMeta: { display: 'flex', gap: '16px', fontSize: '12px', color: '#94a3b8' },
  followupsSection: { marginTop: '24px', paddingTop: '16px', borderTop: '1px solid #e2e8f0' },
  followupsTitle: { margin: '0 0 12px', fontSize: '13px', fontWeight: 600, color: '#334155' },
  followupsList: { display: 'flex', flexWrap: 'wrap', gap: '8px' },
  followupButton: {
    padding: '8px 14px',
    background: '#f1f5f9',
    border: '1px solid #e2e8f0',
    borderRadius: '6px',
    fontSize: '13px',
    color: '#334155',
    cursor: 'pointer',
    transition: 'all 0.15s',
  },
  spellcheck: { marginTop: '16px', padding: '12px', background: '#fef3c7', borderRadius: '8px', fontSize: '13px', color: '#92400e' },
  accessDenied: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '400px',
    textAlign: 'center',
    color: '#64748b',
  },
};