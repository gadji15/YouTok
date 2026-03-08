'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useTranslations } from 'next-intl';

import { Button } from '@/ui/primitives/Button';

export function RetryProjectButton({ projectId }: { projectId: string }) {
  const t = useTranslations('project');
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  return (
    <Button
      type="button"
      disabled={busy}
      onClick={async () => {
        if (busy) return;

        const ok = window.confirm(t('actions.retryConfirm'));
        if (!ok) return;

        setBusy(true);

        try {
          const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}/retry`, {
            method: 'POST',
          });

          if (!res.ok) {
            const message = await res.text();
            throw new Error(message || 'Failed to retry project.');
          }

          router.refresh();
        } catch (err) {
          window.alert(err instanceof Error ? err.message : 'Failed to retry project.');
          setBusy(false);
        }
      }}
    >
      {busy ? t('actions.retrying') : t('actions.retry')}
    </Button>
  );
}
