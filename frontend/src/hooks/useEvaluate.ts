/**
 * Custom hook — wraps the evaluate API call with store state management.
 * Accepts examType so UploadForm can pass it through without touching apiClient.
 */
import { useCallback } from 'react';
import { useEvaluationStore } from '@/store/evaluationStore';
import { submitAnswerForEvaluation } from '@/api';
import { extractApiError } from '@/api';

export function useEvaluate() {
  const { status, result, error, setLoading, setResult, setError, reset } =
    useEvaluationStore();

  const evaluate = useCallback(
    async (
      file: File,
      question: string | null,
      examType: string = 'Custom / General',
    ) => {
      setLoading();
      try {
        const data = await submitAnswerForEvaluation(file, question, examType);
        setResult(data);
      } catch (err) {
        setError(extractApiError(err));
      }
    },
    [setLoading, setResult, setError],
  );

  return { evaluate, status, result, error, reset };
}
