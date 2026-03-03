"use client";

import { NextIntlClientProvider } from "next-intl";

export function IntlProvider({
  locale,
  messages,
  children,
}: {
  locale: string;
  messages: Record<string, any>;
  children: React.ReactNode;
}) {
  // compute defaults for timezone and current time to avoid `ENVIRONMENT_FALLBACK`
  const defaultTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const defaultNow = new Date();

  return (
    <NextIntlClientProvider
      locale={locale}
      messages={messages}
      timeZone={defaultTimeZone}
      now={defaultNow}
      getMessageFallback={({ namespace, key }) =>
        namespace ? `${namespace}.${key}` : key
      }
      onError={(error) => {
        // ignore missing messages since we handle translation keys explicitly
        if (error.message.includes("MISSING_MESSAGE")) return;
        console.error(error);
      }}
    >
      {children}
    </NextIntlClientProvider>
  );
}
