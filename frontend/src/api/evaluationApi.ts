/**
 * Evaluation API — builds the FormData payload and POSTs to /evaluate.
 * exam_type is sent as a form field so the backend picks the right rubric.
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

  const response = await apiClient.post<EvaluateResponse>('/evaluate', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });

  return response.data;
}
