/**
 * Axios instance — hardcoded Render backend URL.
 *
 * Using a hardcoded absolute URL is the most reliable approach:
 *   - Eliminates all env var misconfiguration issues
 *   - Works on Vercel without any environment variable setup
 *   - Works in local dev (CORS is handled by the backend)
 */
import axios, { AxiosError } from 'axios';
import type { ApiError } from '@/types';

// Must have double slashes after https: so Axios knows it is an absolute origin
const BACKEND_URL = 'https://ai-exam-evaluator-chb7.onrender.com/api/v1';

export const apiClient = axios.create({
  baseURL: BACKEND_URL,
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