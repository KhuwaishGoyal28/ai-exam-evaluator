/**
 * Annotation comments with sentiment colouring and paragraph indicator.
 */
import { MessageSquareDot, ThumbsUp, Minus, AlertTriangle } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import type { AnnotationComment, Sentiment } from '@/types';
import { clsx } from 'clsx';

interface AnnotationListProps {
  comments: AnnotationComment[];
}

const SENTIMENT_CONFIG: Record<Sentiment, {
  icon: typeof ThumbsUp;
  bg: string;
  border: string;
  iconColor: string;
}> = {
  positive: { icon: ThumbsUp,       bg: 'bg-emerald-50', border: 'border-emerald-100', iconColor: 'text-emerald-500' },
  neutral:  { icon: Minus,          bg: 'bg-blue-50',    border: 'border-blue-100',    iconColor: 'text-blue-400' },
  negative: { icon: AlertTriangle,  bg: 'bg-rose-50',    border: 'border-rose-100',    iconColor: 'text-rose-500' },
};

export function AnnotationList({ comments }: AnnotationListProps) {
  if (comments.length === 0) return null;

  const positiveCount = comments.filter(c => c.sentiment === 'positive').length;
  const negativeCount = comments.filter(c => c.sentiment === 'negative').length;

  return (
    <Card titleIcon={<MessageSquareDot className="h-4 w-4" />} title="Inline Annotations">
      {/* Summary pills */}
      <div className="mb-4 flex flex-wrap gap-2">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 border border-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          {positiveCount} positive
        </span>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-50 border border-rose-100 px-3 py-1 text-xs font-medium text-rose-700">
          <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
          {negativeCount} needs work
        </span>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-surface-50 border border-surface-200 px-3 py-1 text-xs font-medium text-surface-600">
          {comments.length} total
        </span>
      </div>

      <ul className="space-y-2.5" role="list">
        {comments.map((c, idx) => {
          const config = SENTIMENT_CONFIG[c.sentiment as Sentiment] ?? SENTIMENT_CONFIG.neutral;
          const Icon = config.icon;

          return (
            <li
              key={idx}
              className={clsx(
                'flex items-start gap-3 rounded-xl border p-3.5 transition-all duration-200',
                'hover:shadow-sm animate-in',
                config.bg, config.border,
              )}
              style={{ animationDelay: `${idx * 60}ms` }}
            >
              <div className={clsx('mt-0.5 shrink-0 rounded-lg p-1.5', config.bg)}>
                <Icon className={clsx('h-3.5 w-3.5', config.iconColor)} aria-hidden="true" />
              </div>
              <div className="flex-1 min-w-0 space-y-1.5">
                <p className="text-sm text-surface-800 leading-snug">{c.comment_text}</p>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-surface-400 font-mono">¶{c.paragraph_index + 1}</span>
                  <Badge label={c.sentiment} sentiment={c.sentiment as Sentiment} />
                </div>
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}
