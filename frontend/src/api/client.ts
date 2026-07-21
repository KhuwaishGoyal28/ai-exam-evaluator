import axios, { AxiosError } from 'axios';
import type { ApiError } from '@/types';

export const apiClient = axios.create({
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