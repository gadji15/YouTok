'use client';

import { type FormEvent, useMemo, useState } from 'react';
import { useTranslations } from 'next-intl';
import { useRouter } from 'next/navigation';

import { parseYoutubeVideoId } from '@/lib/youtube';
import { Button } from '@/ui/primitives/Button';
import { Input } from '@/ui/primitives/Input';
import { Select } from '@/ui/primitives/Select';
import { YouTubeEmbed } from '@/ui/shell/YouTubeEmbed';

export function CreateProjectForm({ redirectLocale }: { redirectLocale: string }) {
  const t = useTranslations('projectNew');
  const router = useRouter();

  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [language, setLanguage] = useState<'fr' | 'en'>('fr');
  const [clipLength, setClipLength] = useState('180');
  const [subtitlesEnabled, setSubtitlesEnabled] = useState(true);

  const clipMaxSeconds = useMemo(() => {
    const n = Number.parseInt(clipLength, 10);
    return Number.isFinite(n) ? n : NaN;
  }, [clipLength]);

  const clipLengthOk =
    Number.isFinite(clipMaxSeconds) && clipMaxSeconds >= 60 && clipMaxSeconds <= 180;

  const videoId = useMemo(() => parseYoutubeVideoId(url), [url]);
  const urlOk = videoId !== null;
  const nameOk = name.trim().length > 0;
  const canSubmit = nameOk && urlOk && clipLengthOk;

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!canSubmit || isSubmitting) return;

    setIsSubmitting(true);
    setSubmitError(null);

    const res = await fetch('/api/projects', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name: name.trim(),
        youtube_url: url.trim(),
        language,
        subtitles_enabled: subtitlesEnabled,
        clip_min_seconds: 60,
        clip_max_seconds: clipMaxSeconds,
        subtitle_template: 'modern_karaoke',
      }),
    });

    const json = (await res.json().catch(() => null)) as
      | { id: string }
      | { message?: string; errors?: Record<string, string[]> }
      | null;

    if (!res.ok || !json || !('id' in json)) {
      const message =
        (json && 'message' in json && typeof json.message === 'string' && json.message) ||
        (json && 'errors' in json && json.errors
          ? Object.values(json.errors)
              .flat()
              .filter(Boolean)[0]
          : null) ||
        'Failed to create project.';

      setSubmitError(message);
      setIsSubmitting(false);
      return;
    }

    router.push(`/${redirectLocale}/projects/${json.id}`);
  }

  return (
    <form onSubmit={onSubmit} className="grid gap-5">
      {submitError ? (
        <div className="rounded-xl border border-[color:var(--danger)]/30 bg-[var(--danger)]/10 p-4 text-sm text-[var(--danger)]">
          {submitError}
        </div>
      ) : null}

      <div className="grid gap-2">
        <label className="text-xs font-medium text-[var(--text-muted)]">{t('form.nameLabel')}</label>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t('form.namePlaceholder')}
        />
      </div>

      <div className="grid gap-2">
        <label className="text-xs font-medium text-[var(--text-muted)]">{t('form.urlLabel')}</label>
        <Input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder={t('form.urlPlaceholder')}
        />
        <div
          className={
            'text-xs ' +
            (url.length === 0
              ? 'text-[var(--text-muted)]'
              : urlOk
                ? 'text-[var(--success)]'
                : 'text-[var(--danger)]')
          }
        >
          {url.length === 0 ? ' ' : urlOk ? t('form.urlValid') : t('form.urlInvalid')}
        </div>

        {videoId ? (
          <div className="pt-2 motion-reduce:animate-none sm:animate-[youtok-page-enter_200ms_ease-out]">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-[11px] font-medium text-[var(--text-muted)]">Preview</div>
                <div className="mt-1 text-xs text-[var(--text-muted)]">
                  {t('form.urlValid')}
                </div>
              </div>
              <YouTubeEmbed
                videoId={videoId}
                title={t('form.urlLabel')}
                size="sm"
              />
            </div>
          </div>
        ) : null}
      </div>

      <div className="rounded-xl border border-[color:var(--border)] bg-[var(--surface-muted)] p-4">
        <div className="text-sm font-semibold text-[var(--text)]">{t('form.optionsTitle')}</div>
        <div className="mt-1 text-sm text-[var(--text-muted)]">{t('form.optionsHint')}</div>

        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <div className="grid gap-2">
            <label className="text-xs font-medium text-[var(--text-muted)]">{t('form.languageLabel')}</label>
            <Select value={language} onChange={(e) => setLanguage(e.target.value as 'fr' | 'en')}>
              <option value="fr">FR</option>
              <option value="en">EN</option>
            </Select>
          </div>

          <div className="grid gap-2">
            <label className="text-xs font-medium text-[var(--text-muted)]">{t('form.clipLengthLabel')}</label>
            <Input
              inputMode="numeric"
              min={60}
              max={180}
              value={clipLength}
              onChange={(e) => setClipLength(e.target.value)}
            />
            <div className="text-xs text-[var(--text-muted)]">60–180</div>
          </div>

          <div className="grid gap-2">
            <label className="text-xs font-medium text-[var(--text-muted)]">
              {t('form.subtitlesLabel')}
            </label>
            <Select
              value={subtitlesEnabled ? 'on' : 'off'}
              onChange={(e) => setSubtitlesEnabled(e.target.value === 'on')}
            >
              <option value="on">{t('form.subtitlesOn')}</option>
              <option value="off">{t('form.subtitlesOff')}</option>
            </Select>
          </div>
        </div>
      </div>

      <div className="flex items-center justify-end">
        <Button variant="primary" disabled={!canSubmit || isSubmitting}>
          {t('form.create')}
        </Button>
      </div>
    </form>
  );
}
