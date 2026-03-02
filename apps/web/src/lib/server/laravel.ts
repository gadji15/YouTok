import 'server-only';

type LaravelConfig = {
  baseUrl: string;
  internalApiSecret: string;
};

export function getLaravelConfig(): LaravelConfig {
  return {
    // Use 127.0.0.1 rather than localhost to avoid IPv6/::1 resolution issues on some setups.
    // You can override via LARAVEL_BASE_URL.
    baseUrl: process.env.LARAVEL_BASE_URL ?? 'http://127.0.0.1:8080',
    internalApiSecret: process.env.INTERNAL_API_SECRET ?? 'change-me',
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
