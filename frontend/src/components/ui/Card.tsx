/** Clean card with optional header, icon, and hover lift. */
import { type ReactNode } from 'react';
import { clsx } from 'clsx';

interface CardProps {
  title?: string;
  titleIcon?: ReactNode;
  description?: string;
  children: ReactNode;
  className?: string;
  noPadding?: boolean;
  interactive?: boolean;
}

export function Card({
  title,
  titleIcon,
  description,
  children,
  className,
  noPadding = false,
  interactive = false,
}: CardProps) {
  return (
    <div
      className={clsx(
        'rounded-2xl border border-surface-100 bg-white shadow-card',
        interactive && 'cursor-pointer transition-all duration-300 hover:shadow-card-hover hover:-translate-y-0.5',
        className,
      )}
    >
      {title && (
        <div className="flex items-start gap-3 border-b border-surface-100 px-5 py-4">
          {titleIcon && (
            <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-500">
              {titleIcon}
            </span>
          )}
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-surface-800">{title}</h2>
            {description && (
              <p className="mt-0.5 text-xs text-surface-500">{description}</p>
            )}
          </div>
        </div>
      )}
      <div className={noPadding ? '' : 'p-5'}>{children}</div>
    </div>
  );
}
