/**
 * Axios instance with correct base URL resolution.
 *
 * Priority:
 *   1. VITE_API_BASE_URL env var (must be a full URL like https://...onrender.com/api/v1)
 *   2. /api/v1 relative path — works locally because Vite proxies /api → :8000
 *
 * The _resolveBaseUrl() function ensures we never accidentally create a
 * relative URL when the env var contains a full https:// address.
 */
import axios, { AxiosError } from 'axios';
import type { ApiError } from '@/types';

function resolveBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_BASE_URL;

  // No env var set → local dev, use Vite proxy
  if (!envUrl) return '/api/v1';

  // If it already starts with http:// or https:// → use as-is
  if (envUrl.startsWith('http://') || envUrl.startsWith('https://')) {
    return envUrl;
  }

  // Anything else (malformed, relative) → fall back to local proxy
  return '/api/v1';
}

const BASE_URL = resolveBaseUrl();

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
