/** Animated gradient progress bar with label and score. */
import { clsx } from 'clsx';

interface ProgressBarProps {
  value: number;
  max: number;
  label?: string;
  showScore?: boolean;
  size?: 'sm' | 'md';
}

function getConfig(pct: number) {
  if (pct >= 75) return { fill: 'from-emerald-400 to-teal-500',   text: 'text-emerald-600', bg: 'bg-emerald-50' };
  if (pct >= 50) return { fill: 'from-amber-400  to-orange-400',  text: 'text-amber-600',   bg: 'bg-amber-50'  };
  return               { fill: 'from-rose-400   to-red-500',    text: 'text-rose-600',    bg: 'bg-rose-50'   };
}

export function ProgressBar({ value, max, label, showScore = true, size = 'md' }: ProgressBarProps) {
  const pct  = max > 0 ? Math.round((value / max) * 100) : 0;
  const cfg  = getConfig(pct);
  const h    = size === 'sm' ? 'h-2' : 'h-2.5';

  return (
    <div className="w-full space-y-1.5">
      {(label || showScore) && (
        <div className="flex items-center justify-between gap-2">
          {label && (
            <span className="text-sm font-medium text-surface-700 truncate">{label}</span>
          )}
          {showScore && (
            <span className={clsx('shrink-0 text-xs font-bold tabular-nums', cfg.text)}>
              {value}
              <span className="font-normal text-surface-400">/{max}</span>
            </span>
          )}
        </div>
      )}
      <div
        className={clsx('w-full overflow-hidden rounded-full bg-surface-100', h)}
        role="progressbar"
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-label={label}
      >
        <div
          className={clsx('h-full rounded-full bg-gradient-to-r transition-all duration-700 ease-smooth', cfg.fill)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
