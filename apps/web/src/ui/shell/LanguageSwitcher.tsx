'use client';

import { useLocale } from 'next-intl';
import { usePathname, useRouter } from 'next/navigation';

import { locales, type AppLocale } from '@/i18n/locales';

function setLocaleCookie(locale: AppLocale) {
  document.cookie = `youtok_locale=${locale}; Path=/; Max-Age=${60 * 60 * 24 * 365}; SameSite=Lax`;
}

export function LanguageSwitcher() {
  const locale = useLocale() as AppLocale;
  const router = useRouter();
  const pathname = usePathname();

  function onChange(nextLocale: AppLocale) {
    setLocaleCookie(nextLocale);

    const parts = pathname.split('/');
    if (parts.length > 1 && locales.includes(parts[1] as AppLocale)) {
      parts[1] = nextLocale;
      router.push(parts.join('/') || '/');
      return;
    }

    router.push(`/${nextLocale}${pathname === '/' ? '' : pathname}`);
  }

  return (
    <div className="inline-flex items-center rounded-lg border border-[color:var(--border)] bg-[var(--surface)] p-1 shadow-sm">
      <button
        type="button"
        onClick={() => onChange('fr')}
        className={
          'rounded-md px-2.5 py-1 text-xs font-medium transition-colors motion-reduce:transition-none ' +
          (locale === 'fr'
            ? 'bg-[var(--accent)] text-[var(--accent-foreground)]'
            : 'text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--text)]')
        }
      >
        FR
      </button>
      <button
        type="button"
        onClick={() => onChange('en')}
        className={
          'rounded-md px-2.5 py-1 text-xs font-medium transition-colors motion-reduce:transition-none ' +
          (locale === 'en'
            ? 'bg-[var(--accent)] text-[var(--accent-foreground)]'
            : 'text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--text)]')
        }
      >
        EN
      </button>
    </div>
  );
}
