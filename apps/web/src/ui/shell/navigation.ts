'use client';

import {
  Clapperboard,
  CreditCard,
  FolderKanban,
  LayoutDashboard,
  type LucideIcon,
  Settings,
} from 'lucide-react';

export type AppNavItem = {
  href: string;
  icon: LucideIcon;
  translationKey: string;
};

export const appNavItems: AppNavItem[] = [
  {
    href: '/',
    icon: LayoutDashboard,
    translationKey: 'nav.dashboard',
  },
  {
    href: '/projects',
    icon: FolderKanban,
    translationKey: 'nav.projects',
  },
  {
    href: '/clips',
    icon: Clapperboard,
    translationKey: 'nav.clips',
  },
  {
    href: '/billing',
    icon: CreditCard,
    translationKey: 'nav.billing',
  },
  {
    href: '/settings',
    icon: Settings,
    translationKey: 'nav.settings',
  },
];

export function localizeHref(locale: string, href: string) {
  return `/${locale}${href === '/' ? '' : href}`;
}

function stripTrailingSlash(value: string) {
  if (value.length > 1 && value.endsWith('/')) {
    return value.slice(0, -1);
  }

  return value;
}

export function isNavItemActive({
  pathname,
  locale,
  href,
}: {
  pathname: string;
  locale: string;
  href: string;
}) {
  const current = stripTrailingSlash(pathname);
  const target = stripTrailingSlash(localizeHref(locale, href));

  if (href === '/') {
    return current === `/${locale}`;
  }

  return current === target || current.startsWith(`${target}/`);
}

export const getActiveNavItem = ({
  pathname,
  locale,
}: {
  pathname: string;
  locale: string;
}) => {
  return appNavItems.find((item) => isNavItemActive({ pathname, locale, href: item.href })) || appNavItems[0];
};
