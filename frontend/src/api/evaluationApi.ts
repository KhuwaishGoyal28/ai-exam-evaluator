import type { EvaluateResponse } from '@/types';
import { apiClient } from './client';

// Define the full absolute endpoint URL explicitly
const EVALUATE_URL = 'https://ai-exam-evaluator-chb7.onrender.com/api/v1/evaluate';

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

  // Pass full absolute URL explicitly to override any relative pathing
  const response = await apiClient.post<EvaluateResponse>(EVALUATE_URL, form);

  return response.data;
}