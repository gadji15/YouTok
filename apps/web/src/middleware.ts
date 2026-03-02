import { NextRequest, NextResponse } from 'next/server';

import { defaultLocale, isLocale } from './i18n/locales';

const PUBLIC_FILE = /\.(.*)$/;

function detectLocale(req: NextRequest) {
  const cookieLocale = req.cookies.get('youtok_locale')?.value;
  if (cookieLocale && isLocale(cookieLocale)) {
    return cookieLocale;
  }

  const header = req.headers.get('accept-language') || '';
  const first = header.split(',')[0]?.trim().slice(0, 2);
  if (first && isLocale(first)) {
    return first;
  }

  return defaultLocale;
}

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (
    pathname.startsWith('/_next') ||
    pathname.startsWith('/api') ||
    pathname.startsWith('/favicon') ||
    PUBLIC_FILE.test(pathname)
  ) {
    return NextResponse.next();
  }

  const maybeLocale = pathname.split('/')[1];
  if (maybeLocale && isLocale(maybeLocale)) {
    return NextResponse.next();
  }

  const locale = detectLocale(req);
  const url = req.nextUrl.clone();
  url.pathname = `/${locale}${pathname === '/' ? '' : pathname}`;

  return NextResponse.redirect(url);
}

export const config = {
  matcher: ['/((?!_next|api|favicon.ico).*)'],
};
