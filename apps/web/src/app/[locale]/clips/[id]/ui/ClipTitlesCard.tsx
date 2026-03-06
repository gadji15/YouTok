'use client';

import { useMemo, useState } from 'react';
import { useTranslations } from 'next-intl';

import type { ApiClipTitleCandidates } from '@/lib/api/contracts';
import { Badge } from '@/ui/primitives/Badge';
import { Button } from '@/ui/primitives/Button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/ui/primitives/Card';
import { Input } from '@/ui/primitives/Input';
import { Textarea } from '@/ui/primitives/Textarea';
import { CopyButton } from '@/ui/shell/CopyButton';

function parseHashtags(text: string): string[] {
  const parts = (text || '')
    .split(/\s+/)
    .map((p) => p.trim())
    .filter(Boolean);

  const out: string[] = [];
  for (const p of parts) {
    const s = p.startsWith('#') ? p : `#${p}`;
    if (!out.includes(s)) out.push(s);
    if (out.length >= 10) break;
  }
  return out;
}

export function ClipTitlesCard({
  clipId,
  initialTitle,
  initialCandidates,
}: {
  clipId: string;
  initialTitle: string | null;
  initialCandidates: ApiClipTitleCandidates | null | undefined;
}) {
  const t = useTranslations('clip');

  const [title, setTitle] = useState(initialTitle ?? '');
  const [hashtagsText, setHashtagsText] = useState(
    (initialCandidates?.hashtags ?? []).join(' ')
  );
  const [saving, setSaving] = useState(false);

  const candidates = initialCandidates?.candidates ?? [];

  const analysisLines = useMemo(() => {
    const a = initialCandidates?.analysis;
    if (!a) return [];

    const lines: { label: string; value: string }[] = [];
    if (a.theme) lines.push({ label: t('titles.analysis.theme'), value: a.theme });
    if (a.summary) lines.push({ label: t('titles.analysis.summary'), value: a.summary });
    if (a.clip_key_phrase)
      lines.push({ label: t('titles.analysis.keyPhrase'), value: a.clip_key_phrase });
    return lines;
  }, [initialCandidates?.analysis, t]);

  async function save() {
    if (saving) return;

    setSaving(true);

    try {
      const hashtags = parseHashtags(hashtagsText);

      const res = await fetch(`/api/clips/${encodeURIComponent(clipId)}`, {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ title: title || null, hashtags }),
      });

      if (!res.ok) {
        const message = await res.text();
        throw new Error(message || 'Failed to save title.');
      }
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Failed to save title.');
    } finally {
      setSaving(false);
    }
  }

  async function applyCandidate(nextTitle: string) {
    setTitle(nextTitle);

    try {
      const res = await fetch(`/api/clips/${encodeURIComponent(clipId)}`, {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ title: nextTitle }),
      });

      if (!res.ok) {
        const message = await res.text();
        throw new Error(message || 'Failed to update title.');
      }
    } catch (err) {
      window.alert(err instanceof Error ? err.message : 'Failed to update title.');
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('titles.title')}</CardTitle>
        <CardDescription>{t('titles.subtitle')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-2">
          <div className="text-sm font-medium text-[var(--text)]">{t('titles.editTitle')}</div>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>

        {initialCandidates?.description ? (
          <div className="rounded-lg border border-[color:var(--border)] bg-[var(--surface-muted)] p-3">
            <div className="text-xs font-medium text-[var(--text-muted)]">
              {t('titles.description')}
            </div>
            <p className="mt-2 whitespace-pre-line text-sm text-[var(--text-muted)]">
              {initialCandidates.description}
            </p>
          </div>
        ) : null}

        {analysisLines.length ? (
          <div className="rounded-lg border border-[color:var(--border)] bg-[var(--surface-muted)] p-3">
            <div className="text-xs font-medium text-[var(--text-muted)]">
              {t('titles.analysis.title')}
            </div>
            <div className="mt-2 grid gap-2">
              {analysisLines.map((l) => (
                <div key={l.label} className="flex items-start justify-between gap-3">
                  <div className="text-xs text-[var(--text-muted)]">{l.label}</div>
                  <div className="text-xs font-medium text-[var(--text)]">{l.value}</div>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        <div className="grid gap-2">
          <div className="text-sm font-medium text-[var(--text)]">{t('titles.editHashtags')}</div>
          <Textarea
            value={hashtagsText}
            onChange={(e) => setHashtagsText(e.target.value)}
            placeholder="#pourtoi #islam #rappel"
          />
          <div className="flex items-center justify-end">
            <Button type="button" variant="secondary" disabled={saving} onClick={save}>
              {saving ? t('titles.saving') : t('titles.save')}
            </Button>
          </div>
        </div>

        {candidates.length ? (
          <div className="grid gap-2">
            <div className="text-sm font-medium text-[var(--text)]">{t('titles.alternatives')}</div>
            {candidates.slice(0, 8).map((c, idx) => (
              <div
                key={`${idx}-${c.title}`}
                className="flex items-start justify-between gap-3 rounded-lg border border-[color:var(--border)] bg-[var(--surface)] p-3"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <div className="truncate text-sm font-medium text-[var(--text)]">
                      {c.title}
                    </div>
                    <Badge variant="secondary" className="shrink-0">
                      {t('titles.score', { value: Math.round(c.score * 100) })}
                    </Badge>
                  </div>
                </div>

                <div className="flex shrink-0 flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="primary"
                    onClick={() => applyCandidate(c.title)}
                  >
                    {t('titles.use')}
                  </Button>
                  <CopyButton
                    text={c.title}
                    label={t('titles.copy')}
                    copiedLabel={t('titles.copied')}
                  />
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-[var(--text-muted)]">{t('titles.empty')}</div>
        )}
      </CardContent>
    </Card>
  );
}
