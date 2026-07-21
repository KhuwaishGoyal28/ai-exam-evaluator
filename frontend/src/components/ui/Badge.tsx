/** Sentiment-aware badge pill. */
import { clsx } from 'clsx';
import type { Sentiment } from '@/types';

interface BadgeProps {
  label: string;
  sentiment?: Sentiment;
  variant?: 'solid' | 'soft';
  className?: string;
}

const SENTIMENT_SOFT: Record<Sentiment, string> = {
  positive: 'bg-emerald-50 text-emerald-700 border border-emerald-200',
  neutral:  'bg-blue-50   text-blue-700   border border-blue-200',
  negative: 'bg-rose-50   text-rose-700   border border-rose-200',
};
const SENTIMENT_DOT: Record<Sentiment, string> = {
  positive: 'bg-emerald-400',
  neutral:  'bg-blue-400',
  negative: 'bg-rose-400',
};

export function Badge({ label, sentiment, variant = 'soft', className }: BadgeProps) {
  const cls = sentiment
    ? SENTIMENT_SOFT[sentiment]
    : 'bg-surface-100 text-surface-600 border border-surface-200';
  const dot = sentiment ? SENTIMENT_DOT[sentiment] : 'bg-surface-400';

  return (
    <span className={clsx(
      'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5',
      'text-[11px] font-semibold capitalize tracking-wide',
      cls,
      className,
    )}>
      <span className={clsx('h-1.5 w-1.5 shrink-0 rounded-full', dot)} />
      {label}
    </span>
  );
}
