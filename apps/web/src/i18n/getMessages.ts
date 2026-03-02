import fr from './messages/fr.json';
import en from './messages/en.json';
import type { AppLocale } from './locales';

export function getMessages(locale: AppLocale) {
  return locale === 'en' ? en : fr;
}
