'use client';

import Link from 'next/link';
import { useLocale, useTranslations } from 'next-intl';
import { usePathname } from 'next/navigation';

import type { AppLocale } from '@/i18n/locales';
import { cn } from '@/lib/cn';
import { Logo } from '@/ui/shell/Logo';
import { appNavItems, isNavItemActive, localizeHref } from '@/ui/shell/navigation';

export function SidebarContent({
  onNavigate,
}: {
  onNavigate?: () => void;
}) {
  const t = useTranslations('app');
  const locale = useLocale() as AppLocale;
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-14 items-center gap-2 px-4">
        <Logo />
        <div className="text-sm font-semibold tracking-tight">{t('name')}</div>
      </div>

      <nav className="px-2 py-3">
        {appNavItems.map((item) => {
          const href = localizeHref(locale, item.href);
          const active = isNavItemActive({ pathname, locale, href: item.href });
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={href}
              onClick={onNavigate}
              className={cn(
                'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                active
                  ? 'bg-[var(--surface-muted)] text-[var(--text)]'
                  : 'text-[var(--text-muted)] hover:bg-[var(--surface-muted)] hover:text-[var(--text)]'
              )}
            >
              <Icon
                className={cn(
                  'h-4 w-4',
                  active ? 'text-[var(--text)]' : 'text-[var(--text-muted)]'
                )}
              />
              <span className="truncate">{t(item.translationKey)}</span>
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto px-4 pb-4 pt-2">
        <div className="rounded-lg border border-[color:var(--border)] bg-[var(--surface-muted)] p-3">
          <div className="text-xs font-medium text-[var(--text)]">Workspace</div>
          <div className="mt-1 truncate text-sm text-[var(--text-muted)]">demo.youtok.com</div>
        </div>
      </div>
    </div>
  );
}
