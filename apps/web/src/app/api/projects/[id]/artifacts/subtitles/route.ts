import { laravelInternalFetch } from '@/lib/server/laravel';

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  const res = await laravelInternalFetch(`/api/projects/${encodeURIComponent(id)}/artifacts/subtitles`, {
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

  return new Response(res.body, {
    status: res.status,
    headers: {
      'content-type': res.headers.get('content-type') ?? 'text/plain; charset=utf-8',
      'content-disposition':
        res.headers.get('content-disposition') ??
        'attachment; filename="subtitles.srt"',
    },
  });
}
