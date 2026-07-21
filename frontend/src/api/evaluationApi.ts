import type { EvaluateResponse } from '@/types';
import { apiClient } from './client';

const API_ENDPOINT = 'https://ai-exam-evaluator-chb7.onrender.com/api/v1/evaluate';

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

  // Passing full absolute URL directly to avoid baseURL prefixing
  const response = await apiClient.post<EvaluateResponse>(API_ENDPOINT, form);

  return response.data;
}