/**
 * Axios instance.
 *
 * Base URL strategy:
 *   - Always use '/api/v1' (relative path).
 *   - On Vercel: vercel.json rewrites /api/v1/* → https://render-backend/api/v1/*
 *   - In local dev: Vite vite.config.ts proxies /api → http://localhost:8000
 *
 * This means NO environment variable is needed — routing is handled
 * at the infrastructure level (Vercel rewrites / Vite proxy).
 */
import axios, { AxiosError } from 'axios';
import type { ApiError } from '@/types';

export const apiClient = axios.create({
  baseURL: '/api/v1',
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
