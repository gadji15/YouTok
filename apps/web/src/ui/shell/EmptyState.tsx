import type { ReactNode } from 'react';

import Link from 'next/link';

import { cn } from '@/lib/cn';
import { buttonStyles } from '@/ui/primitives/buttonStyles';

export function EmptyState({
  title,
  description,
  icon,
  actionLabel,
  actionHref,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  icon?: ReactNode;
  actionLabel?: ReactNode;
  actionHref?: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'rounded-xl border border-[color:var(--border)] bg-[var(--surface)] p-6 text-center',
        className
      )}
    >
      {icon ? <div className="mx-auto flex h-10 w-10 items-center justify-center text-[var(--text-muted)]">{icon}</div> : null}
      <div className="mt-3 text-sm font-semibold text-[var(--text)]">{title}</div>
      {description ? <div className="mt-1 text-sm text-[var(--text-muted)]">{description}</div> : null}
      {actionHref && actionLabel ? (
        <div className="mt-4 flex justify-center">
          <Link href={actionHref} className={buttonStyles({ variant: 'primary', size: 'sm' })}>
            {actionLabel}
          </Link>
        </div>
      ) : null}
    </div>
  );
}
