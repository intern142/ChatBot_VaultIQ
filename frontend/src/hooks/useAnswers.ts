import { useState, useCallback } from 'react';
import { askQuestion } from '@/api/answers';
import type { AnswerResponse } from '@/api/types';

export function useAnswers() {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState<AnswerResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ask = useCallback(async (questionText: string) => {
    if (!questionText.trim()) return;
    setLoading(true);
    setError(null);
    setAnswer(null);
    try {
      const response = await askQuestion({ question: questionText, top_k: 10, hybrid_weight: 0.5 });
      setAnswer(response);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleQuestionChange = (value: string) => {
    setQuestion(value);
  };

  const clearAnswer = () => {
    setAnswer(null);
    setError(null);
    setQuestion('');
  };

  return {
    question,
    setQuestion: handleQuestionChange,
    answer,
    loading,
    error,
    ask,
    clearAnswer,
  };
}