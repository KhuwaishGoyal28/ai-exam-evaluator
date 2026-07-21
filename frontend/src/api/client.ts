/**
 * Axios instance with base URL + error normalisation.
 * All API modules import from here — never create raw axios instances elsewhere.
 */
import axios, { AxiosError } from 'axios';
import type { ApiError } from '@/types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 120_000, // OCR + LLM can take ~60s
});

/** Extract a normalised ApiError from any Axios error. */
export function extractApiError(err: unknown): ApiError {
  if (err instanceof AxiosError && err.response?.data?.error) {
    return err.response.data.error as ApiError;
  }
  return {
    code: 'UNKNOWN_ERROR',
    message: err instanceof Error ? err.message : 'An unexpected error occurred.',
  };
}
