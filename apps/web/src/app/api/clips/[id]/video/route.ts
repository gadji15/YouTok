import { laravelInternalFetch } from '@/lib/server/laravel';

export async function GET(
  req: Request,
  { params }: { params: Promise<{ id?: string }> }
) {
  const { id } = await params;
  if (!id) {
    return new Response('Missing clip id.', { status: 400 });
  }

  const range = req.headers.get('range');

  const res = await laravelInternalFetch(`/api/clips/${encodeURIComponent(id)}/video`, {
    headers: range ? { range } : undefined,
  });

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
