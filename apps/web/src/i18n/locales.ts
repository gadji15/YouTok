export const locales = ['fr', 'en'] as const;
export type AppLocale = (typeof locales)[number];

export const defaultLocale: AppLocale = 'fr';

export function isLocale(value: string): value is AppLocale {
  return (locales as readonly string[]).includes(value);
}
