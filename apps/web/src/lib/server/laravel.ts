import 'server-only';

type LaravelConfig = {
  baseUrl: string;
  internalApiSecret: string;
};

const DEFAULT_INTERNAL_API_SECRET = 'change-me';

export function getLaravelConfig(): LaravelConfig {
  const baseUrl = process.env.LARAVEL_BASE_URL ?? 'http://127.0.0.1:8080';
  const internalApiSecret = process.env.INTERNAL_API_SECRET ?? DEFAULT_INTERNAL_API_SECRET;

  if (process.env.NODE_ENV === 'production') {
    if (!internalApiSecret || internalApiSecret === DEFAULT_INTERNAL_API_SECRET) {
      throw new Error('INTERNAL_API_SECRET must be set to a non-default value in production');
    }
  }

  return {
    // Use 127.0.0.1 rather than localhost to avoid IPv6/::1 resolution issues on some setups.
    // You can override via LARAVEL_BASE_URL.
    baseUrl,
    internalApiSecret,
  };
}

export async function laravelInternalFetch(
  path: string,
  init: RequestInit = {}
): Promise<Response> {
  const { baseUrl, internalApiSecret } = getLaravelConfig();
  const url = new URL(path, baseUrl);

  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');
  headers.set('X-Internal-Secret', internalApiSecret);

  try {
    return await fetch(url, {
      ...init,
      headers,
      cache: init.cache ?? 'no-store',
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);

    const maybeCause = (error instanceof Error ? (error as any).cause : undefined) as unknown;
    const causeMessage =
      maybeCause instanceof Error
        ? maybeCause.message
        : typeof maybeCause === 'string'
          ? maybeCause
          : null;

    throw new Error(
      `laravelInternalFetch failed (${url.toString()}): ${message}${causeMessage ? ` (${causeMessage})` : ''}`,
      {
        cause: error,
      }
    );
  }
}
