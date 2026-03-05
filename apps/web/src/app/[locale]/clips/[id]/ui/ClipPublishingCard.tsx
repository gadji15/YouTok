'use client';

import { useEffect, useMemo, useState } from 'react';
import { useTranslations } from 'next-intl';

import type {
  ApiTikTokAccount,
  ApiTikTokAccountsIndexResponse,
} from '@/lib/api/contracts';
import { Badge } from '@/ui/primitives/Badge';
import { Button } from '@/ui/primitives/Button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/ui/primitives/Card';
import { Select } from '@/ui/primitives/Select';
import { Textarea } from '@/ui/primitives/Textarea';

type PublishStatus = string | null;

export function ClipPublishingCard({
  clipId,
  initialCaption,
  initialAccountId,
  initialPublishStatus,
  initialPublishJobId,
  initialPublishError,
  initialPublishedAt,
  canPublish,
}: {
  clipId: string;
  initialCaption: string | null;
  initialAccountId: string | null;
  initialPublishStatus: PublishStatus;
  initialPublishJobId: string | null;
  initialPublishError: string | null;
  initialPublishedAt: string | null;
  canPublish: boolean;
}) {
  const t = useTranslations('clip');

  const [caption, setCaption] = useState(initialCaption ?? '');
  const [saving, setSaving] = useState(false);

  const [accounts, setAccounts] = useState<ApiTikTokAccount[] | null>(null);
  const [accountsError, setAccountsError] = useState<string | null>(null);
  const [accountId, setAccountId] = useState<string>(initialAccountId ?? '');

  const [publishing, setPublishing] = useState(false);
  const [status, setStatus] = useState<PublishStatus>(initialPublishStatus);
  const [jobId, setJobId] = useState<string | null>(initialPublishJobId);
  const [publishError, setPublishError] = useState<string | null>(initialPublishError);
  const [publishedAt, setPublishedAt] = useState<string | null>(initialPublishedAt);

  const activeAccounts = useMemo(() => {
    return (accounts ?? []).filter((a) => a.status === 'active');
  }, [accounts]);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        setAccountsError(null);
        const res = await fetch('/api/tiktok-accounts');
        const json = (await res.json()) as ApiTikTokAccountsIndexResponse;
        if (!res.ok) {
          throw new Error('Failed to load TikTok accounts.');
        }

        if (!cancelled) {
          setAccounts(json.data);
        }
      } catch (err) {
        if (!cancelled) {
          setAccounts([]);
          setAccountsError(err instanceof Error ? err.message : 'Failed to load TikTok accounts.');
        }
      }
    }

    run();

    return () => {
      cancelled = true;
    };
  }, []);

  async function saveCaption() {
    if (saving) return;

    setSaving(true);

    try {
      const res = await fetch(`/api/clips/${encodeURIComponent(clipId)}`, {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ tiktok_caption: caption }),
      });

      if (!res.ok) {
        const message = await res.text();
        throw new Error(message || 'Failed to save caption.');
      }
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Failed to save caption.');
    } finally {
      setSaving(false);
    }
  }

  async function refreshPublishStatus() {
    try {
      const res = await fetch(`/api/clips/${encodeURIComponent(clipId)}/publish/status`);
      const json = (await res.json()) as {
        status?: string | null;
        job_id?: string | null;
        error?: string | null;
        published_at?: string | null;
      };

      if (!res.ok) {
        const message = await res.text();
        throw new Error(message || 'Failed to refresh publish status.');
      }

      setStatus(json.status ?? null);
      setJobId(json.job_id ?? null);
      setPublishError(json.error ?? null);
      setPublishedAt(json.published_at ?? null);
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Failed to refresh publish status.');
    }
  }

  async function publish() {
    if (publishing) return;

    if (!accountId) {
      window.alert(t('publishing.errors.missingAccount'));
      return;
    }

    setPublishing(true);

    try {
      const res = await fetch(`/api/clips/${encodeURIComponent(clipId)}/publish`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ tiktok_account_id: accountId, caption }),
      });

      const text = await res.text();
      let json: unknown = null;
      try {
        json = text ? JSON.parse(text) : null;
      } catch {
        // ignore
      }

      if (!res.ok) {
        const message =
          typeof json === 'object' &&
          json &&
          'error' in json &&
          typeof (json as { error: unknown }).error === 'string'
            ? ((json as { error: string }).error || text)
            : text;

        throw new Error(message || 'Failed to publish clip.');
      }

      const parsed =
        typeof json === 'object' && json ? (json as { status?: unknown; job_id?: unknown }) : {};

      setStatus(typeof parsed.status === 'string' ? parsed.status : 'queued');
      setJobId(typeof parsed.job_id === 'string' ? parsed.job_id : null);
      setPublishError(null);

      await refreshPublishStatus();
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Failed to publish clip.');
    } finally {
      setPublishing(false);
    }
  }

  const statusBadgeVariant: 'success' | 'danger' | 'warning' | 'secondary' =
    status === 'completed'
      ? 'success'
      : status === 'failed'
        ? 'danger'
        : status
          ? 'warning'
          : 'secondary';

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('publishing.title')}</CardTitle>
        <CardDescription>{t('publishing.subtitle')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2">
          <div className="text-sm font-medium text-[var(--text)]">
            {t('publishing.captionLabel')}
          </div>
          <Textarea
            value={caption}
            onChange={(e) => setCaption(e.target.value)}
            placeholder={t('publishing.captionPlaceholder')}
          />
          <div className="flex items-center justify-between gap-2">
            <div className="text-xs text-[var(--text-muted)]">
              {t('publishing.captionHint')}
            </div>
            <Button type="button" variant="secondary" disabled={saving} onClick={saveCaption}>
              {saving ? t('publishing.saving') : t('publishing.save')}
            </Button>
          </div>
        </div>

        <div className="grid gap-2">
          <div className="text-sm font-medium text-[var(--text)]">
            {t('publishing.accountLabel')}
          </div>
          <Select
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            disabled={accounts === null}
          >
            <option value="">{t('publishing.accountPlaceholder')}</option>
            {activeAccounts.map((account) => (
              <option key={account.id} value={account.id}>
                @{account.username}
              </option>
            ))}
          </Select>
          {accountsError ? (
            <div className="text-xs text-[var(--danger)]">{accountsError}</div>
          ) : null}
        </div>

        <div className="rounded-lg border border-[color:var(--border)] bg-[var(--surface-muted)] p-3">
          <div className="flex items-center justify-between gap-3">
            <div className="text-sm font-medium text-[var(--text)]">
              {t('publishing.statusLabel')}
            </div>
            <Badge variant={statusBadgeVariant}>{status ?? '—'}</Badge>
          </div>
          {jobId ? (
            <div className="mt-1 text-xs text-[var(--text-muted)]">job: {jobId}</div>
          ) : null}
          {publishedAt ? (
            <div className="mt-1 text-xs text-[var(--text-muted)]">
              {t('publishing.publishedAt', { value: publishedAt })}
            </div>
          ) : null}
          {publishError ? (
            <div className="mt-2 text-xs text-[var(--danger)]">{publishError}</div>
          ) : null}

          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              type="button"
              variant="primary"
              disabled={!canPublish || publishing}
              onClick={publish}
            >
              {publishing ? t('publishing.publishing') : t('publishing.publish')}
            </Button>
            <Button type="button" variant="secondary" onClick={refreshPublishStatus}>
              {t('publishing.refresh')}
            </Button>
          </div>

          {!canPublish ? (
            <div className="mt-2 text-xs text-[var(--text-muted)]">
              {t('publishing.disabledHint')}
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
