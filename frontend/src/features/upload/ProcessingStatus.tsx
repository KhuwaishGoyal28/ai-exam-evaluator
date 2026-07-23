/**
 * Animated step-by-step processing indicator.
 * Shows pipeline stages with timing-based active state.
 * Multi-page handwritten PDFs take 1–5 minutes depending on page count.
 */
import { Loader2, CheckCircle2, Upload, ScanText, Brain, Pencil } from 'lucide-react';
import { clsx } from 'clsx';

const STEPS = [
  { label: 'Uploading to secure storage',     sub: 'Saving your answer sheet',                    icon: Upload,   delay: 0 },
  { label: 'Reading handwriting (page 1…)',   sub: 'AI Vision OCR — one page at a time',          icon: ScanText, delay: 4_000 },
  { label: 'Evaluating against rubric',       sub: 'Scoring all parameters (this takes a while)', icon: Brain,    delay: 30_000 },
  { label: 'Generating annotated PDF',        sub: 'Adding red-ink marks and score sheet',        icon: Pencil,   delay: 90_000 },
];

interface ProcessingStatusProps {
  elapsedMs: number;
}

export function ProcessingStatus({ elapsedMs }: ProcessingStatusProps) {
  const activeStep = STEPS.reduce((acc, step, idx) => {
    return elapsedMs >= step.delay ? idx : acc;
  }, 0);

  // Estimate: 4 pages × ~20s/page = ~80s typical
  const estimatedSec = 90;
  const pct = Math.min(99, Math.round((elapsedMs / 1000 / estimatedSec) * 100));

  return (
    <div className="overflow-hidden rounded-2xl border border-brand-100 bg-gradient-to-br from-brand-50 to-indigo-50">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-brand-100/60 px-5 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-500 shadow-glow">
          <Loader2 className="h-4 w-4 animate-spin text-white" />
        </div>
        <div>
          <p className="text-sm font-semibold text-brand-800">Processing your answer sheet…</p>
          <p className="text-xs text-brand-500">
            Multi-page PDFs take 1–5 minutes · please keep this tab open
          </p>
        </div>
        <div className="ml-auto text-xs font-mono text-brand-400 tabular-nums">
          {Math.floor(elapsedMs / 1000)}s
        </div>
      </div>

      {/* Steps */}
      <div className="px-5 py-4 space-y-1">
        {STEPS.map((step, idx) => {
          const isDone    = idx < activeStep;
          const isActive  = idx === activeStep;
          const isPending = idx > activeStep;
          const Icon = step.icon;

          return (
            <div
              key={step.label}
              className={clsx(
                'flex items-center gap-3 rounded-xl px-3 py-2.5 transition-all duration-500',
                isActive  && 'bg-white shadow-sm',
                isDone    && 'opacity-60',
                isPending && 'opacity-35',
              )}
            >
              <div className={clsx(
                'flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-all duration-300',
                isDone    && 'bg-emerald-100',
                isActive  && 'bg-brand-100',
                isPending && 'bg-surface-100',
              )}>
                {isDone ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                ) : (
                  <Icon className={clsx(
                    'h-4 w-4',
                    isActive ? 'text-brand-500 animate-pulse-slow' : 'text-surface-400',
                  )} />
                )}
              </div>

              <div className="min-w-0">
                <p className={clsx(
                  'text-sm font-medium leading-none',
                  isDone    ? 'text-surface-500 line-through decoration-1'
                            : isActive ? 'text-surface-800' : 'text-surface-400',
                )}>
                  {step.label}
                </p>
                {isActive && (
                  <p className="mt-1 text-xs text-brand-500 animate-in">{step.sub}</p>
                )}
              </div>

              {isActive && (
                <Loader2 className="ml-auto h-4 w-4 shrink-0 animate-spin text-brand-400" />
              )}
            </div>
          );
        })}
      </div>

      {/* Progress bar */}
      <div className="px-5 pb-4">
        <div className="h-1.5 w-full rounded-full bg-brand-100 overflow-hidden">
          <div
            className="h-full rounded-full bg-brand-500 transition-all duration-1000"
            style={{ width: `${pct}%` }}
          />
        </div>
        <p className="mt-1.5 text-right text-xs text-brand-400 tabular-nums">{pct}%</p>
      </div>
    </div>
  );
}