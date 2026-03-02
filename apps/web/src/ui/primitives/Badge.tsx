import * as React from 'react';

import { cn } from '@/lib/cn';

type BadgeVariant = 'default' | 'secondary' | 'success' | 'warning' | 'danger';

export function Badge({
  className,
  variant = 'default',
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: BadgeVariant }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium',
        {
          default:
            'border-[color:var(--border)] bg-[var(--surface-muted)] text-[var(--text-muted)]',
          secondary:
            'border-[color:var(--border)] bg-[var(--surface)] text-[var(--text-muted)]',
          success: 'border-[color:var(--border)] bg-[var(--success-soft)] text-[var(--text)]',
          warning: 'border-[color:var(--border)] bg-[var(--warning-soft)] text-[var(--text)]',
          danger: 'border-[color:var(--border)] bg-[var(--danger-soft)] text-[var(--text)]',
        }[variant],
        className
      )}
      {...props}
    />
  );
}
