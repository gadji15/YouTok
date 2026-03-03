'use client';

import { NextIntlClientProvider } from 'next-intl';

export function IntlProvider({
  locale,
  messages,
  children,
}: {
  locale: string;
  messages: Record<string, any>;
  children: React.ReactNode;
}) {
  return (
    <NextIntlClientProvider
      locale={locale}
      messages={messages}
      getMessageFallback={({ namespace, key }) => (namespace ? `${namespace}.${key}` : key)}
      onError={(error) => {
        if (error.message.includes('MISSING_MESSAGE')) return;
        console.error(error);
      }}
    >
      {children}
    </NextIntlClientProvider>
  );
}
