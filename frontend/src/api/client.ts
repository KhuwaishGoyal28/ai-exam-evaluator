/**
 * Axios instance with base URL + error normalisation.
 *
 * URL resolution:
 *   - If VITE_API_BASE_URL is set (Vercel production) → use it directly
 *     e.g. https://ai-exam-evaluator-chb7.onrender.com/api/v1
 *   - If not set (local dev) → use relative /api/v1 which Vite proxies to :8000
 */
import axios, { AxiosError } from 'axios';
import type { ApiError } from '@/types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 120_000,
});

export function extractApiError(err: unknown): ApiError {
  if (err instanceof AxiosError && err.response?.data?.error) {
    return err.response.data.error as ApiError;
  }
  return {
    code: 'UNKNOWN_ERROR',
    message: err instanceof Error ? err.message : 'An unexpected error occurred.',
  };
}
