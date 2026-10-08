import { useAuth } from '@/context/AuthContext';
import { useSearch } from '@/hooks/useSearch';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { Alert } from '@/components/ui/Alert';
import { EmptyState } from '@/components/ui/EmptyState';
import type { SearchResult } from '@/api/types';

export default function SearchPage() {
  const { role } = useAuth();
  const {
    query,
    setQuery,
    results,
    loading,
    suggestLoading,
    error,
    suggestions,
    showSuggestions,
  } = useSearch();

  const isClientAdminOrEmployee = role === 'client_admin' || role === 'employee';
  const isSuperAdmin = role === 'super_admin';

  if (isSuperAdmin) {
    return (
      <div style={styles.container}>
        <div style={styles.accessDenied}>
          <h2>Access Denied</h2>
          <p>Super Admin cannot access tenant search. This feature is for tenant users only.</p>
        </div>
      </div>
    );
  }

  if (!isClientAdminOrEmployee) {
    return (
      <div style={styles.container}>
        <div style={styles.accessDenied}>
          <h2>Access Denied</h2>
          <p>You don't have permission to access search.</p>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.header}>
        <h1 style={styles.title}>Search</h1>
        <p style={styles.subtitle}>Search across your organization's documents</p>
      </div>

      <form style={styles.searchForm}>
        <div style={styles.searchInputWrapper}>
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search documents..."
            style={styles.searchInput}
            disabled={loading}
            autoComplete="off"
            aria-autocomplete="list"
            aria-controls="suggestions-list"
            aria-expanded={showSuggestions && suggestions.length > 0}
          />
          {suggestLoading && <Spinner size="sm" style={styles.searchSpinner} />}
          <Button
            type="button"
            loading={loading}
            disabled={!query.trim() || loading}
            style={styles.searchButton}
            onClick={() => {}}
          >
            Search
          </Button>
        </div>

        {showSuggestions && suggestions.length > 0 && (
          <ul id="suggestions-list" style={styles.suggestionsList} role="listbox">
            {suggestions.map((suggestion, index) => (
              <li key={index} role="option" style={styles.suggestionItem} onClick={() => { setQuery(suggestion); document.querySelector('form')?.requestSubmit(); }}>
                {suggestion}
              </li>
            ))}
          </ul>
        )}
      </form>

      {error && <Alert variant="error" onDismiss={() => setQuery('')}>{error}</Alert>}

      <div style={styles.resultsSection}>
        {loading ? (
          <div style={styles.loading}>
            <Spinner size="lg" />
            <span>Searching...</span>
          </div>
        ) : query.trim() && results.length === 0 ? (
          <EmptyState
            icon="🔍"
            title="No results found"
            description="Try different keywords or check your spelling"
            action={query.trim() ? { label: 'Clear', onClick: () => setQuery('') } : undefined}
          />
        ) : results.length > 0 ? (
          <div style={styles.resultsList}>
            {results.map((result, index) => (
              <SearchResultCard key={`${result.document_id}-${result.chunk_index}-${index}`} result={result} />
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

interface SearchResultCardProps {
  result: SearchResult;
}

function SearchResultCard({ result }: SearchResultCardProps) {
  return (
    <div style={styles.resultCard}>
      <div style={styles.resultHeader}>
        <span style={styles.resultFilename}>{result.original_filename}</span>
        <span style={styles.resultScore}>Score: {(result.score * 100).toFixed(1)}%</span>
      </div>
      <p style={styles.resultContent}>{result.content}</p>
      <div style={styles.resultMeta}>
        <span>Document ID: {result.document_id.slice(0, 8)}...</span>
        <span>Chunk: {result.chunk_index}</span>
      </div>
    </div>
  );
}

interface SearchResultCardProps {
  result: SearchResult;
}

const styles: Record<string, React.CSSProperties> = {
  container: { padding: '24px', maxWidth: '900px', margin: '0 auto' },
  header: { marginBottom: '24px' },
  title: { margin: '0 0 8px', fontSize: '24px', fontWeight: 700, color: '#0f172a' },
  subtitle: { margin: 0, fontSize: '14px', color: '#64748b' },
  searchForm: { marginBottom: '24px' },
  searchInputWrapper: {
    display: 'flex',
    gap: '12px',
    alignItems: 'center',
    position: 'relative',
  },
  searchInput: {
    flex: 1,
    padding: '12px 16px',
    border: '1px solid #cbd5e1',
    borderRadius: '8px',
    fontSize: '16px',
    fontFamily: 'inherit',
    outline: 'none',
    transition: 'border-color 0.15s, box-shadow 0.15s',
  },
  searchSpinner: { position: 'absolute', right: '56px' },
  searchButton: { height: '48px', padding: '0 24px' },
  suggestionsList: {
    position: 'absolute',
    top: '100%',
    left: 0,
    right: '60px',
    marginTop: '4px',
    background: 'white',
    border: '1px solid #e2e8f0',
    borderRadius: '8px',
    boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
    listStyle: 'none',
    padding: '4px',
    maxHeight: '200px',
    overflowY: 'auto',
    zIndex: 10,
  },
  suggestionItem: {
    padding: '10px 12px',
    cursor: 'pointer',
    borderRadius: '6px',
    fontSize: '14px',
    color: '#334155',
    transition: 'background 0.1s',
  },
  resultsSection: { marginTop: '24px' },
  loading: { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px', padding: '48px', color: '#64748b' },
  resultsList: { display: 'flex', flexDirection: 'column', gap: '12px' },
  resultCard: {
    padding: '16px',
    background: 'white',
    border: '1px solid #e2e8f0',
    borderRadius: '8px',
    transition: 'box-shadow 0.15s',
  },
  resultHeader: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' },
  resultFilename: { fontSize: '14px', fontWeight: 500, color: '#0f172a' },
  resultScore: { fontSize: '12px', color: '#64748b', background: '#f1f5f9', padding: '2px 8px', borderRadius: '4px' },
  resultContent: { margin: '0 0 8px', fontSize: '14px', color: '#334155', lineHeight: '1.5' },
  resultMeta: { display: 'flex', gap: '16px', fontSize: '12px', color: '#94a3b8' },
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