import { cn } from '@/lib/cn';

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-md bg-[var(--border)] opacity-70',
        'motion-reduce:animate-none',
        className
      )}
    />
  );
}
