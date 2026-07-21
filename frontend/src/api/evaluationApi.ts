/**
 * Evaluation API — builds the FormData payload and POSTs to /evaluate.
 *
 * IMPORTANT: Do NOT manually set Content-Type header for multipart/form-data.
 * Axios must set it automatically so it includes the correct `boundary` value.
 * Without the boundary, the server cannot parse the form fields.
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

  // No Content-Type header — axios sets it automatically with the correct boundary
  const response = await apiClient.post<EvaluateResponse>('/evaluate', form);

  return response.data;
}
