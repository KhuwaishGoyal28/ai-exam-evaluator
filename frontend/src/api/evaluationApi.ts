/**
 * Evaluation API — builds the FormData payload and POSTs to /evaluate.
 *
 * IMPORTANT: Do NOT manually set Content-Type header for multipart/form-data.
 * Axios sets it automatically with the correct `boundary` parameter.
 */
import type { EvaluateResponse } from '@/types';
import { apiClient } from './client';

export async function submitAnswerForEvaluation(
  file: File,
  question: string | null,
  examType: string = 'Custom / General',
): Promise<EvaluateResponse> {
  const form = new FormData();
  form.append('file', file);
  form.append('exam_type', examType);
  if (question?.trim()) {
    form.append('question', question.trim());
  }

  // Calls https://ai-exam-evaluator-chb7.onrender.com/api/v1/evaluate
  const response = await apiClient.post<EvaluateResponse>('/evaluate', form);

  return response.data;
}