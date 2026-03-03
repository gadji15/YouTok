'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useTranslations } from 'next-intl';

import { Button } from '@/ui/primitives/Button';

export function DeleteProjectButton({
  projectId,
  redirectHref,
}: {
  projectId: string;
  redirectHref: string;
}) {
  const t = useTranslations('project');
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  return (
    <Button
      type="button"
      variant="danger"
      disabled={busy}
      onClick={async () => {
        if (busy) return;

        const ok = window.confirm(t('actions.deleteConfirm'));
        if (!ok) return;

        setBusy(true);

        try {
          const res = await fetch(`/api/projects/${encodeURIComponent(projectId)}`, {
            method: 'DELETE',
          });

          if (!res.ok) {
            const message = await res.text();
            throw new Error(message || 'Failed to delete project.');
          }

          router.push(redirectHref);
          router.refresh();
        } catch (err) {
          window.alert(err instanceof Error ? err.message : 'Failed to delete project.');
          setBusy(false);
        }
      }}
    >
      {busy ? t('actions.deleting') : t('actions.delete')}
    </Button>
  );
}
