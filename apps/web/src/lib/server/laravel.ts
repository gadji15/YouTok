import 'server-only';

type LaravelConfig = {
  baseUrl: string;
  internalApiSecret: string;
};

const DEFAULT_INTERNAL_API_SECRET = 'change-me';
const DEFAULT_INTERNAL_API_SECRET_PREFIX = 'please-ch  const
export function getLaravelConfig(): LaravelConfig {
  const baseUrl = process.env.LARAVEL_BASE_URL ?? 'http://127.0.0.1:8080';
  const internalApiSecret = proce  if (process.env.NODE_ENV === 'production') {
    if (
      !internalApiSecret ||
      internalApiSecret === DEFAULT_INTERNAL_API_SECRET ||
      internalApiSecret.startsWith(DEFAULT_INTERNAL_API_SECRET_PREFIX)
    ) {
      throw new Error('INTERNAL_API_SECRET must be set to a non-default v
  return {
    // Use 127.0.0.1
  return {
    // Use 127.0.0.1 rather than localhost to avoid IPv6/::1 resolution issues on some setups.
    // You can override via LARAVEL_BASE_URL.
    baseU}

export async function laravel}

export async function laravelInternalFetch(
  path: string,
  init: RequestInit = {}
): Promise<Response> {
  const { baseUrl, internalApiSecret } = getLaravelConfig();
  const url = new URL(path, baseUrl);

  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  headers.set('X-Internal-Secret    return await fetch(
  try {
    return await fetch(url,         ...init,
      headers,
      cache: init.cache ?? 'no-stor        });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);

    const maybeCause = (error instanceof Error ? (error as any).cause : undefined) as unknown;
    const causeMessage =
      maybeCause instanceof Error
        ? maybeCause.message
        : typeof maybeCause === 'string'
              throw new              `lar
    throw new Error(
      `laravelInternalFetch failed (${url.toString()}): ${message}${causeMessage ? ` (${causeMessage})` : ''}`                 }
}
se: error,
      }
    );
  }
}
