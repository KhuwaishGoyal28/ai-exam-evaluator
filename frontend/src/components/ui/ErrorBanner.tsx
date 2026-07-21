/** Error banner with icon, message, and optional retry. */
import { XCircle, RotateCcw } from 'lucide-react';
import type { ApiError } from '@/types';

interface ErrorBannerProps {
  error: ApiError;
  onRetry?: () => void;
}

export function ErrorBanner({ error, onRetry }: ErrorBannerProps) {
  const title = error.code
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <div
      role="alert"
      className="animate-in flex items-start gap-3 rounded-2xl border border-danger-200 bg-danger-50 p-4"
    >
      <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-danger-500" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-danger-800">{title}</p>
        <p className="mt-0.5 text-sm text-danger-600">{error.message}</p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="shrink-0 flex items-center gap-1.5 rounded-lg border border-danger-200 bg-white px-3 py-1.5 text-xs font-semibold text-danger-600 hover:bg-danger-50 transition-colors duration-200"
        >
          <RotateCcw className="h-3 w-3" />
          Retry
        </button>
      )}
    </div>
  );
}
