import type { Metadata } from 'next';
import { Plus_Jakarta_Sans } from 'next/font/google';
import { NextIntlClientProvider } from 'next-intl';

import '../globals.css';
import { getMessages } from '../../i18n/getMessages';
import { isLocale, type AppLocale } from '../../i18n/locales';
import { AppShell } from '@/ui/shell/AppShell';
import { PageTransition } from '@/ui/shell/PageTransition';
import { ThemeProvider } from '@/ui/theme/ThemeProvider';
import { ThemeScript } from '@/ui/theme/ThemeScript';

const sans = Plus_Jakarta_Sans({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-sans',
});

export const metadata: Metadata = {
  title: 'YouTok',
  description: 'AI Clip SaaS',
};

export default async function RootLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale: rawLocale } = await params;
  const locale: AppLocale = isLocale(rawLocale) ? rawLocale : 'fr';

  const messages = getMessages(locale);

  return (
    <html lang={locale} className={sans.variable} suppressHydrationWarning>
      <head>
        <ThemeScript />
      </head>
      <body>
        <ThemeProvider>
          <NextIntlClientProvider locale={locale} messages={messages}>
            <AppShell>
              <PageTransition>{children}</PageTransition>
            </AppShell>
          </NextIntlClientProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
