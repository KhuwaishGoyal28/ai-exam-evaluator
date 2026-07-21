/**
 * Animated step-by-step processing indicator.
 * Shows four pipeline stages with timing-based active state.
 */
import { Loader2, CheckCircle2, Upload, ScanText, Brain, Pencil } from 'lucide-react';
import { clsx } from 'clsx';

const STEPS = [
  { label: 'Uploading to secure storage',   sub: 'Saving your answer sheet',          icon: Upload,    delay: 0 },
  { label: 'Extracting text via OCR',        sub: 'Reading handwritten content',       icon: ScanText,  delay: 4000 },
  { label: 'AI rubric evaluation',           sub: 'Scoring against 5 parameters',     icon: Brain,     delay: 14000 },
  { label: 'Generating annotated image',     sub: 'Adding margin comments',           icon: Pencil,    delay: 38000 },
];

interface ProcessingStatusProps {
  elapsedMs: number;
}

export function ProcessingStatus({ elapsedMs }: ProcessingStatusProps) {
  const activeStep = STEPS.reduce((acc, step, idx) => {
    return elapsedMs >= step.delay ? idx : acc;
  }, 0);

  return (
    <div className="overflow-hidden rounded-2xl border border-brand-100 bg-gradient-to-br from-brand-50 to-indigo-50">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-brand-100/60 px-5 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-500 shadow-glow">
          <Loader2 className="h-4 w-4 animate-spin text-white" />
        </div>
        <div>
          <p className="text-sm font-semibold text-brand-800">Processing your answer…</p>
          <p className="text-xs text-brand-500">This takes 30–60 seconds</p>
        </div>
        <div className="ml-auto text-xs font-mono text-brand-400 tabular-nums">
          {Math.floor(elapsedMs / 1000)}s
        </div>
      </div>

      {/* Steps */}
      <div className="px-5 py-4 space-y-1">
        {STEPS.map((step, idx) => {
          const isDone = idx < activeStep;
          const isActive = idx === activeStep;
          const isPending = idx > activeStep;
          const Icon = step.icon;

          return (
            <div
              key={step.label}
              className={clsx(
                'flex items-center gap-3 rounded-xl px-3 py-2.5 transition-all duration-500',
                isActive && 'bg-white shadow-sm',
                isDone && 'opacity-60',
                isPending && 'opacity-35',
              )}
            >
              {/* Step indicator */}
              <div className={clsx(
                'flex h-8 w-8 shrink-0 items-center justify-center rounded-full transition-all duration-300',
                isDone && 'bg-emerald-100',
                isActive && 'bg-brand-100',
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

              {/* Text */}
              <div className="min-w-0">
                <p className={clsx(
                  'text-sm font-medium leading-none',
                  isDone ? 'text-surface-500 line-through decoration-1' : isActive ? 'text-surface-800' : 'text-surface-400',
                )}>
                  {step.label}
                </p>
                {isActive && (
                  <p className="mt-1 text-xs text-brand-500 animate-in">{step.sub}</p>
                )}
              </div>

              {/* Active spinner */}
              {isActive && (
                <Loader2 className="ml-auto h-4 w-4 shrink-0 animate-spin text-brand-400" />
              )}
            </div>
          );
        })}
      </div>

      {/* Progress dots */}
      <div className="flex items-center gap-2 border-t border-brand-100/60 px-5 py-3">
        {STEPS.map((_, idx) => (
          <div
            key={idx}
            className={clsx(
              'h-1.5 rounded-full transition-all duration-500',
              idx < activeStep ? 'bg-emerald-400 w-6' :
              idx === activeStep ? 'bg-brand-500 w-8 animate-pulse' :
              'bg-surface-200 w-3',
            )}
          />
        ))}
      </div>
    </div>
  );
}
