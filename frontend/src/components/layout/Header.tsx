/**
 * Sticky header — frosted glass, violet/teal theme.
 * No "AI" or exam-specific branding in the nav.
 */
import { ClipboardCheck, Star } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import { clsx } from 'clsx';

export function Header() {
  const { pathname } = useLocation();
  const isResults = pathname === '/results';

  return (
    <header className="sticky top-0 z-50 w-full">
      {/* Thin top gradient bar */}
      <div className="h-[3px] w-full bg-gradient-to-r from-violet-600 via-teal-400 to-cyan-500" />

      {/* Glass nav */}
      <div className="glass shadow-sm border-b border-white/30">
        <div className="container-pad">
          <div className="flex h-16 items-center justify-between gap-4">

            {/* Brand mark */}
            <Link
              to="/"
              className="group flex shrink-0 items-center gap-3 focus-visible:outline-none"
              aria-label="EvalPro home"
            >
              <div className={clsx(
                'flex h-9 w-9 items-center justify-center rounded-xl',
                'bg-gradient-to-br from-violet-500 to-teal-500',
                'shadow-md transition-all duration-300',
                'group-hover:scale-105 group-hover:shadow-glow',
              )}>
                <ClipboardCheck className="h-5 w-5 text-white" aria-hidden="true" />
              </div>

              <div className="flex flex-col leading-tight">
                <span className="text-[15px] font-extrabold tracking-tight text-slate-900">
                  Eval<span className="text-grad-primary">Pro</span>
                </span>
                <span className="text-[10px] font-medium tracking-widest text-slate-400 uppercase">
                  Smart Evaluator
                </span>
              </div>

              <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-violet-200 bg-violet-50 px-2.5 py-1 text-[11px] font-semibold text-violet-700">
                <Star className="h-3 w-3 fill-current" />
                Smart Scoring
              </span>
            </Link>

            {/* Right */}
            {isResults && (
              <Link
                to="/"
                className={clsx(
                  'inline-flex items-center gap-2 rounded-xl px-4 py-2',
                  'border border-slate-200 bg-white text-sm font-semibold text-slate-700',
                  'shadow-xs hover:border-violet-200 hover:bg-violet-50 hover:text-violet-700',
                  'transition-all duration-200',
                )}
              >
                ← New Evaluation
              </Link>
            )}

          </div>
        </div>
      </div>
    </header>
  );
}
