import { Check, Loader2, X } from 'lucide-react';

import { cn } from '@/lib/cn';
import { Progress } from '@/ui/primitives/Progress';

export type PipelineStageStatus = 'pending' | 'active' | 'done' | 'failed';

export type PipelineStage = {
  key: string;
  label: string;
  status: PipelineStageStatus;
};

export function PipelineProgress({
  value,
  stages,
  className,
}: {
  value: number;
  stages: PipelineStage[];
  className?: string;
}) {
  const clamped = Math.min(100, Math.max(0, value));

  return (
    <div className={cn('space-y-3', className)}>
      <Progress value={clamped} />

      <div className="relative">
        <div className="absolute inset-x-0 top-2 h-px bg-[color:var(--border)]" />
        <div
          className="absolute left-0 top-2 h-px bg-[var(--accent)] transition-[width] duration-500 motion-reduce:transition-none"
          style={{ width: `${clamped}%` }}
          aria-hidden
        />

        <div className={cn('relative z-10 grid gap-2', gridColsClass(stages.length))}>
          {stages.map((stage) => (
            <div key={stage.key} className="flex flex-col items-center gap-1">
              <StageDot status={stage.status} />
              <div className="text-center text-[11px] font-medium text-[var(--text-muted)]">
                {stage.label}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function StageDot({ status }: { status: PipelineStageStatus }) {
  const base =
    'flex h-5 w-5 items-center justify-center rounded-full border shadow-sm';

  if (status === 'done') {
    return (
      <span className={cn(base, 'border-transparent bg-[var(--accent)] text-[var(--accent-foreground)]')}>
        <Check className="h-3 w-3" />
      </span>
    );
  }

  if (status === 'failed') {
    return (
      <span className={cn(base, 'border-transparent bg-[var(--danger)] text-white')}>
        <X className="h-3 w-3" />
      </span>
    );
  }

  if (status === 'active') {
    return (
      <span
        className={cn(
          base,
          'border-[color:var(--border)] bg-[var(--surface)] text-[var(--accent)]'
        )}
      >
        <Loader2 className="h-3 w-3 animate-spin motion-reduce:animate-none" />
      </span>
    );
  }

  return (
    <span
      className={cn(
        base,
        'border-[color:var(--border)] bg-[var(--surface)] text-[var(--text-muted)]'
      )}
    />
  );
}

function gridColsClass(count: number) {
  if (count <= 3) return 'grid-cols-3';
  if (count === 4) return 'grid-cols-4';
  if (count === 6) return 'grid-cols-6';
  return 'grid-cols-5';
}
