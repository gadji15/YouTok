export function parseYoutubeVideoId(input: string): string | null {
  const trimmed = input.trim();
  if (trimmed.length === 0) return null;

  let url: URL;
  try {
    url = new URL(trimmed);
  } catch {
    return null;
  }

  const hostname = url.hostname.toLowerCase().replace(/^www\./, '');

  let id: string | null = null;

  if (hostname === 'youtu.be') {
    id = url.pathname.split('/').filter(Boolean)[0] ?? null;
  } else if (
    hostname.endsWith('youtube.com') ||
    hostname.endsWith('youtube-nocookie.com')
  ) {
    if (url.pathname === '/watch') {
      id = url.searchParams.get('v');
    } else if (url.pathname.startsWith('/shorts/')) {
      id = url.pathname.split('/').filter(Boolean)[1] ?? null;
    } else if (url.pathname.startsWith('/embed/')) {
      id = url.pathname.split('/').filter(Boolean)[1] ?? null;
    } else if (url.pathname.startsWith('/live/')) {
      id = url.pathname.split('/').filter(Boolean)[1] ?? null;
    } else if (url.pathname.startsWith('/v/')) {
      id = url.pathname.split('/').filter(Boolean)[1] ?? null;
    }
  }

  if (!id) return null;

  // Strip extra path segments just in case.
  id = id.split('?')[0]?.split('&')[0] ?? id;

  // YouTube IDs are typically 11 chars.
  if (!/^[a-zA-Z0-9_-]{11}$/.test(id)) return null;

  return id;
}

export function youtubeEmbedUrl(videoId: string) {
  const params = new URLSearchParams({
    rel: '0',
    modestbranding: '1',
    playsinline: '1',
  });

  return `https://www.youtube-nocookie.com/embed/${videoId}?${params.toString()}`;
}
