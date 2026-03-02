import { getRequestConfig } from 'next-intl/server';

import { getMessages } from '@/i18n/getMessages';
import { defaultLocale, isLocale } from '@/i18n/locales';

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale = requested && isLocale(requested) ? requested : defaultLocale;

  return {
    locale,
    messages: getMessages(locale),
  };
});
