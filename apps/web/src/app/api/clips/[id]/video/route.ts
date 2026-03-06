import { laravelInternalFetch } from '@/lib/server/laravel';

export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  const range = req.headers.get('range');

  const res = await laravelInternalFetch(`/api/clips/${encodeURIComponent(id)}/video`, {
    headers: range ? { range } : undefined,
    redirect: 'manual',
  });

  const location = res.headers.get('location');
  if (location && res.status >= 300 && res.status < 400) {
    return new Response(null, {
      status: res.status,
      headers: {
        location,
      },
    });
  }

  const headers: Record<string, string> = {
    'content-type': res.headers.get('content-type') ?? 'video/mp4',
    'content-disposition': res.headers.get('content-disposition') ?? 'inline',
  };

  for (const key of ['accept-ranges', 'content-range', 'content-length']) {
    const value = res.headers.get(key);
    if (value) {
      headers[key] = value;
    }
  }

  return new Response(res.body, {
    status: res.status,
    headers,
  });
}
