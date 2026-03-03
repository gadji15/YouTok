'use client';

import Link from 'next/link';
import { type ReactNode, useEffect, useMemo, useState } from 'react';
import { useLocale, useTranslations } from 'next-intl';

import type { ApiClipsIndexResponse, ApiClipStatus } from '@/lib/api/contracts';

import type { AppLocale } from '@/i18n/locales';
import { Badge } from '@/ui/primitives/Badge';
import { Button } from '@/ui/primitives/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/ui/primitives/Card';
import { Input } from '@/ui/primitives/Input';
import { buttonStyles } from '@/ui/primitives/buttonStyles';
import { EmptyState } from '@/ui/shell/EmptyState';

type ClipStatus = ApiClipStatus;

type ClipRow = {
  id: string;
  title: string;
  projectName: string;
  status: ClipStatus;
  durationSec: number;
  createdAt: string | null;
};

export function ClipsIndex() {
  const t = useTranslations('clips');
  const tClip = useTranslations('clip');
  const locale = useLocale() as AppLocale;

  const [clips, setClips] = useState<ClipRow[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<'all' | ClipStatus>('all');
  const [view, setView] = useState<'table' | 'cards'>('table');

  useEffect(() => {
    let cancelled = false;

    async function run() {
      try {
        setLoadError(null);
        const res = await fetch('/api/clips');
        const json = (await res.json()) as ApiClipsIndexResponse;
        if (!res.ok) {
          throw new Error('Failed to load clips.');
        }

        const rows: ClipRow[] = json.data.map((c) => ({
          id: c.id,
          title: c.title ?? c.id,
          projectName: c.project_name ?? '—',
          status: c.status,
          durationSec: c.duration_seconds ? Math.round(c.duration_seconds) : 0,
          createdAt: c.created_at,
        }));

        if (!cancelled) {
          setClips(rows);
        }
      } catch (err) {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : 'Failed to load clips.');
          setClips([]);
        }
      }
    }

    run();

    return () => {
      cancelled = true;
    };
  }, []);

  const df = useMemo(
    () =>
      new Intl.DateTimeFormat(locale, {
        dateStyle: 'medium',
        timeStyle: 'short',
      }),
    [locale]
  );

  const allClips = useMemo(() => clips ?? [], [clips]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();

    return allClips.filter((clip) => {
      if (status !== 'all' && clip.status !== status) return false;
      if (q.length === 0) return true;

      return (
        clip.id.toLowerCase().includes(q) ||
        clip.title.toLowerCase().includes(q) ||
        clip.projectName.toLowerCase().includes(q)
      );
    });
  }, [allClips, query, status]);

  const hasAny = allClips.length > 0;

  return (
    <Card>
      <CardHeader className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <CardTitle>{t('listTitle')}</CardTitle>
          <div className="mt-1 text-sm text-[var(--text-muted)]">
            {clips === null
              ? t('countEmpty')
              : hasAny
                ? t('count', { shown: filtered.length, total: allClips.length })
                : t('countEmpty')}
          </div>
        </div>

        <div className="flex w-full flex-col gap-3 sm:flex-row sm:items-center lg:w-auto">
          <div className="w-full sm:w-72">
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t('searchPlaceholder')}
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <FilterButton active={status === 'all'} onClick={() => setStatus('all')}>
              {t('filters.all')}
            </FilterButton>
            <FilterButton active={status === 'pending'} onClick={() => setStatus('pending')}>
              {t('filters.pending')}
            </FilterButton>
            <FilterButton active={status === 'ready'} onClick={() => setStatus('ready')}>
              {t('filters.ready')}
            </FilterButton>
            <FilterButton active={status === 'failed'} onClick={() => setStatus('failed')}>
              {t('filters.failed')}
            </FilterButton>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setView('table')}
              className={buttonStyles({ variant: view === 'table' ? 'primary' : 'secondary', size: 'sm' })}
            >
              {t('view.table')}
            </button>
            <button
              type="button"
              onClick={() => setView('cards')}
              className={buttonStyles({ variant: view === 'cards' ? 'primary' : 'secondary', size: 'sm' })}
            >
              {t('view.cards')}
            </button>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        {loadError ? (
          <div className="rounded-xl border border-[color:var(--danger)]/30 bg-[var(--danger)]/10 p-4 text-sm text-[var(--danger)]">
            {loadError}
          </div>
        ) : clips === null ? (
          <div className="rounded-xl border border-[color:var(--border)] bg-[var(--surface-muted)] p-6 text-sm text-[var(--text-muted)]">
            Loading…
          </div>
        ) : !hasAny ? (
          <EmptyState
            title={t('empty.title')}
            description={t('empty.subtitle')}
            actionLabel={t('empty.action')}
            actionHref={`/${locale}/projects`}
          />
        ) : filtered.length === 0 ? (
          <div className="rounded-xl border border-[color:var(--border)] bg-[var(--surface-muted)] p-6">
            <div className="text-sm font-semibold text-[var(--text)]">{t('noResults.title')}</div>
            <div className="mt-1 text-sm text-[var(--text-muted)]">{t('noResults.subtitle')}</div>
            <div className="mt-4 flex items-center gap-2">
              <Button
                onClick={() => {
                  setQuery('');
                  setStatus('all');
                }}
              >
                {t('noResults.reset')}
              </Button>
            </div>
          </div>
        ) : view === 'table' ? (
          <div className="overflow-hidden rounded-lg border border-[color:var(--border)] bg-[var(--surface)]">
            <div className="grid grid-cols-12 bg-[var(--surface-muted)] px-4 py-2 text-xs font-medium text-[var(--text-muted)]">
              <div className="col-span-5">{t('table.clip')}</div>
              <div className="col-span-3">{t('table.project')}</div>
              <div className="col-span-2">{t('table.status')}</div>
              <div className="col-span-1 text-right">{t('table.duration')}</div>
              <div className="col-span-1 text-right">{t('table.created')}</div>
            </div>

            <div className="divide-y divide-[color:var(--border)]">
              {filtered.map((clip) => (
                <Link
                  key={clip.id}
                  href={`/${locale}/clips/${clip.id}`}
                  className="grid grid-cols-12 items-center gap-3 px-4 py-3 text-sm transition-colors hover:bg-[var(--surface-muted)] motion-reduce:transition-none"
                >
                  <div className="col-span-5 min-w-0">
                    <div className="truncate font-medium text-[var(--text)]">{clip.title}</div>
                    <div className="mt-0.5 truncate text-xs text-[var(--text-muted)]">{clip.id}</div>
                  </div>
                  <div className="col-span-3 min-w-0">
                    <div className="truncate text-sm text-[var(--text-muted)]">{clip.projectName}</div>
                  </div>
                  <div className="col-span-2">
                    <StatusBadge
                      status={clip.status}
                      labels={{
                        pending: tClip('status.pending'),
                        ready: tClip('status.ready'),
                        failed: tClip('status.failed'),
                      }}
                    />
                  </div>
                  <div className="col-span-1 text-right text-xs text-[var(--text-muted)]">
                    {formatDuration(clip.durationSec)}
                  </div>
                  <div className="col-span-1 text-right text-xs text-[var(--text-muted)]">
                    {clip.createdAt ? df.format(new Date(clip.createdAt)) : '—'}
                  </div>
                </Link>
              ))}
            </div>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((clip) => (
              <Link
                key={clip.id}
                href={`/${locale}/clips/${clip.id}`}
                className="group rounded-xl border border-[color:var(--border)] bg-[var(--surface)] p-4 shadow-sm transition hover:-translate-y-px hover:border-[color:var(--border)] hover:shadow motion-reduce:transition-none motion-reduce:hover:translate-y-0"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold text-[var(--text)] group-hover:text-[var(--accent)]">
                      {clip.title}
                    </div>
                    <div className="mt-1 truncate text-xs text-[var(--text-muted)]">{clip.projectName}</div>
                  </div>
                  <StatusBadge
                    status={clip.status}
                    labels={{
                      pending: tClip('status.pending'),
                      ready: tClip('status.ready'),
                      failed: tClip('status.failed'),
                    }}
                  />
                </div>

                <div className="mt-4 grid grid-cols-2 gap-3 rounded-lg border border-[color:var(--border)] bg-[var(--surface-muted)] p-3 text-xs">
                  <div>
                    <div className="text-[var(--text-muted)]">{t('cards.duration')}</div>
                    <div className="mt-1 font-medium text-[var(--text)]">
                      {formatDuration(clip.durationSec)}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-[var(--text-muted)]">{t('cards.created')}</div>
                    <div className="mt-1 font-medium text-[var(--text)]">{clip.createdAt ? df.format(new Date(clip.createdAt)) : '—'}</div>
                  </div>
                </div>

                <div className="mt-3 truncate text-xs text-[var(--text-muted)]">{clip.id}</div>
              </Link>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={buttonStyles({ variant: active ? 'primary' : 'secondary', size: 'sm' })}
    >
      {children}
    </button>
  );
}

function StatusBadge({
  status,
  labels,
}: {
  status: ClipStatus;
  labels: Record<ClipStatus, string>;
}) {
  const variant =
    status === 'ready' ? 'success' : status === 'failed' ? 'danger' : 'warning';

  return <Badge variant={variant}>{labels[status]}</Badge>;
}

function formatDuration(totalSeconds: number) {
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}m ${seconds.toString().padStart(2, '0')}s`;
}


