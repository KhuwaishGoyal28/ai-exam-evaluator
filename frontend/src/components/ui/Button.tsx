/**
 * Button — primary, secondary, ghost, danger variants with sizes.
 */
import { type ButtonHTMLAttributes, type ReactNode } from 'react';
import { clsx } from 'clsx';
import { Loader2 } from 'lucide-react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline';
  size?: 'xs' | 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  leftIcon?: ReactNode;
  rightIcon?: ReactNode;
  children: ReactNode;
}

const VARIANTS: Record<string, string> = {
  primary: [
    'bg-gradient-to-r from-brand-500 to-brand-600 text-white',
    'hover:from-brand-600 hover:to-brand-700',
    'shadow-md hover:shadow-glow active:scale-[0.98]',
    'disabled:from-surface-200 disabled:to-surface-200 disabled:text-surface-400 disabled:shadow-none',
  ].join(' '),
  secondary: [
    'bg-white border border-surface-200 text-surface-700',
    'hover:bg-surface-50 hover:border-brand-200 hover:text-brand-700',
    'shadow-xs active:scale-[0.98]',
    'disabled:opacity-50 disabled:cursor-not-allowed',
  ].join(' '),
  outline: [
    'border-2 border-brand-300 text-brand-600 bg-transparent',
    'hover:bg-brand-50 hover:border-brand-400',
    'active:scale-[0.98]',
    'disabled:opacity-50',
  ].join(' '),
  ghost: [
    'text-surface-600 bg-transparent',
    'hover:bg-surface-100 hover:text-surface-900',
    'disabled:opacity-50',
  ].join(' '),
  danger: [
    'bg-danger-500 text-white',
    'hover:bg-danger-600 shadow-xs active:scale-[0.98]',
    'disabled:opacity-50',
  ].join(' '),
};

const SIZES: Record<string, string> = {
  xs: 'h-7  px-3   text-xs  rounded-lg  gap-1.5',
  sm: 'h-8  px-3.5 text-xs  rounded-lg  gap-2',
  md: 'h-10 px-4   text-sm  rounded-xl  gap-2',
  lg: 'h-12 px-6   text-sm  rounded-xl  gap-2.5 font-semibold',
};

export function Button({
  variant = 'primary',
  size = 'md',
  isLoading = false,
  leftIcon,
  rightIcon,
  disabled,
  className,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      disabled={disabled || isLoading}
      className={clsx(
        'inline-flex items-center justify-center font-medium',
        'transition-all duration-200 outline-none',
        'focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2',
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    >
      {isLoading
        ? <Loader2 className="h-4 w-4 animate-spin-slow shrink-0" aria-hidden="true" />
        : leftIcon
          ? <span className="shrink-0">{leftIcon}</span>
          : null
      }
      <span>{children}</span>
      {rightIcon && !isLoading && <span className="shrink-0">{rightIcon}</span>}
    </button>
  );
}
