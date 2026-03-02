'use client';

import { useTranslations } from 'next-intl';

import { buttonStyles } from '@/ui/primitives/buttonStyles';
import { useTheme, type ThemePreference } from '@/ui/theme/ThemeProvider';

export function ThemeSegmentedControl() {
  const t = useTranslations('settings');
  const { preference, setPreference } = useTheme();

  const options: Array<{ value: ThemePreference; label: string }> = [
    { value: 'system', label: t('theme.options.system') },
    { value: 'light', label: t('theme.options.light') },
    { value: 'dark', label: t('theme.options.dark') },
  ];

  return (
    <div className="inline-flex rounded-xl border border-[color:var(--border)] bg-[var(--surface)] p-1">
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => setPreference(opt.value)}
          className={buttonStyles({
            variant: preference === opt.value ? 'primary' : 'secondary',
            size: 'sm',
          })}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
