'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useTranslations } from 'next-intl';

import { Button } from '@/ui/primitives/Button';

export function DeleteClipButton({
  clipId,
  redirectHref,
}: {
  clipId: string;
  redirectHref: string;
}) {
  const t = useTranslations('clip');
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
          const res = await fetch(`/api/clips/${encodeURIComponent(clipId)}`, {
            method: 'DELETE',
          });

          if (!res.ok) {
            const message = await res.text();
            throw new Error(message || 'Failed to delete clip.');
          }

          router.push(redirectHref);
          router.refresh();
        } catch (err) {
          window.alert(err instanceof Error ? err.message : 'Failed to delete clip.');
          setBusy(false);
        }
      }}
    >
      {busy ? t('actions.deleting') : t('actions.delete')}
    </Button>
  );
}
