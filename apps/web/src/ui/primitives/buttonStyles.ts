import { cn } from '../../lib/cn';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

export function buttonStyles({
  variant = 'secondary',
  size = 'md',
  className,
}: {
  variant?: ButtonVariant;
  size?: ButtonSize;
  className?: string;
}) {
  return cn(
    'inline-flex items-center justify-center gap-2 rounded-lg font-medium shadow-sm transition-all ring-offset-[color:var(--surface)]',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--focus-ring)] focus-visible:ring-offset-2',
    'disabled:pointer-events-none disabled:opacity-50',
    'active:translate-y-px',
    'motion-reduce:transition-none motion-reduce:active:translate-y-0',
    {
      primary: 'bg-[var(--accent)] text-[var(--accent-foreground)] hover:opacity-90',
      secondary:
        'border border-[color:var(--border)] bg-[var(--surface)] text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--text)]',
      ghost: 'text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--text)]',
      danger: 'bg-[var(--danger)] text-white hover:opacity-90',
    }[variant],
    {
      sm: 'h-9 px-3 text-sm',
      md: 'h-10 px-3.5 text-sm',
      lg: 'h-11 px-4 text-sm',
    }[size],
    className
  );
}
