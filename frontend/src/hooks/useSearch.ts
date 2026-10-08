import { useState, useCallback } from 'react';
import { search, suggest } from '@/api/search';
import type { SearchResult } from '@/api/types';

export function useSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [suggestLoading, setSuggestLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSuggestions, setShowSuggestions] = useState(false);

  const performSearch = useCallback(async () => {
    if (!query.trim()) {
      setResults([]);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await search({ query, top_k: 10, hybrid_weight: 0.5 });
      setResults(response.results);
    } catch (err: any) {
      setError(err.message);
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [query]);

  const performSuggest = useCallback(async () => {
    if (!query.trim() || query.length < 2) {
      setSuggestions([]);
      return;
    }
    setSuggestLoading(true);
    try {
      const response = await suggest({ query, limit: 5 });
      setSuggestions(response.suggestions);
      setShowSuggestions(true);
    } catch {
      setSuggestions([]);
    } finally {
      setSuggestLoading(false);
    }
  }, [query]);

  const handleQueryChange = (value: string) => {
    setQuery(value);
    if (value.length >= 2) {
      performSuggest();
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  };

  return {
    query,
    setQuery: handleQueryChange,
    results,
    loading,
    suggestLoading,
    error,
    suggestions,
    showSuggestions,
    setShowSuggestions,
    performSearch,
    clearResults: () => {
      setResults([]);
      setError(null);
      setQuery('');
      setSuggestions([]);
      setShowSuggestions(false);
    },
  };
}