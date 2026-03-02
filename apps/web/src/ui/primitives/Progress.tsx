import { cn } from '@/lib/cn';

type ProgressVariant = 'accent' | 'success' | 'warning' | 'danger';

export function Progress({
  value,
  variant = 'accent',
  className,
}: {
  value: number;
  variant?: ProgressVariant;
  className?: string;
}) {
  const clamped = Math.min(100, Math.max(0, value));

  const barColor =
    variant === 'success'
      ? 'bg-[var(--success)]'
      : variant === 'warning'
        ? 'bg-[var(--warning)]'
        : variant === 'danger'
          ? 'bg-[var(--danger)]'
          : 'bg-[var(--accent)]';

  return (
    <div
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn(
        'h-2 w-full overflow-hidden rounded-full bg-[var(--surface-muted)]',
        className
      )}
    >
      <div
        className={cn(
          'h-full rounded-full transition-[width] duration-500 ease-out motion-reduce:transition-none',
          barColor
        )}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
