'use client';

import { Menu } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { usePathname } from 'next/navigation';

import type { AppLocale } from '../../i18n/locales';
import { LanguageSwitcher } from './LanguageSwitcher';
import { getActiveNavItem } from './navigation';

export function Topbar({
  onOpenMobileNav,
}: {
  onOpenMobileNav?: () => void;
}) {
  const t = useTranslations('app');
  const locale = useLocale() as AppLocale;
  const pathname = usePathname();
  const active = getActiveNavItem({ pathname, locale });

  return (
    <header className="sticky top-0 z-10 border-b border-[color:var(--border)] bg-[var(--surface-overlay)] backdrop-blur">
      <div className="flex h-14 items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex min-w-0 items-center gap-3">
          <button
            type="button"
            onClick={onOpenMobileNav}
            aria-label={t('topbar.openNavigation')}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[color:var(--border)] bg-[var(--surface)] text-[var(--text-muted)] shadow-sm transition-colors hover:bg-[var(--surface-muted)] hover:text-[var(--text)] lg:hidden"
          >
            <Menu className="h-4 w-4" />
          </button>

          <div className="hidden text-sm font-medium text-[var(--text)] sm:block">YouTok</div>
          <div className="hidden h-5 w-px bg-[color:var(--border)] sm:block" />
          <div className="truncate text-sm font-medium text-[var(--text-muted)]">{t(active.translationKey)}</div>
        </div>

        <div className="flex items-center gap-3">
          <LanguageSwitcher />
          <button
            type="button"
            className="inline-flex items-center rounded-lg border border-[color:var(--border)] bg-[var(--surface)] px-3 py-2 text-sm font-medium text-[var(--text-muted)] shadow-sm transition-colors hover:bg-[var(--surface-muted)] hover:text-[var(--text)]"
          >
            {t('topbar.account')}
          </button>
        </div>
      </div>
    </header>
  );
}
