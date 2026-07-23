import axios, { AxiosError } from 'axios';
import type { ApiError } from '@/types';

// Handwritten PDF evaluation can take up to 8-10 minutes on a free-tier backend
// (one Groq Vision call per page + 5s delay between pages to respect rate limits).
// 10 minutes is enough for a 6-page document.
export const apiClient = axios.create({
  timeout: 600_000,   // 10 minutes
});

export function extractApiError(err: unknown): ApiError {
  if (err instanceof AxiosError) {
    // Axios timeout
    if (err.code === 'ECONNABORTED' || err.message.includes('timeout')) {
      return {
        code: 'TIMEOUT',
        message:
          'The evaluation is taking longer than expected. ' +
          'This is normal for multi-page PDFs — each page takes ~15 seconds. ' +
          'Please try again with fewer pages, or wait a moment and retry.',
      };
    }
    if (err.response?.data?.error) {
      return err.response.data.error as ApiError;
    }
  }
  return {
    code: 'UNKNOWN_ERROR',
    message: err instanceof Error ? err.message : 'An unexpected error occurred.',
  };
}