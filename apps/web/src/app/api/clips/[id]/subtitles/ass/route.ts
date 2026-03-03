import { laravelInternalFetch } from '@/lib/server/laravel';

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id?: string }> }
) {
  const { id } = await params;
  if (!id) {
    return new Response('Missing clip id.', { status: 400 });
  }

  const res = await laravelInternalFetch(
    `/api/clips/${encodeURIComponent(id)}/subtitles.ass`
  );

  return new Response(res.body, {
    status: res.status,
    headers: {
      'content-type': res.headers.get('content-type') ?? 'text/plain; charset=utf-8',
      'content-disposition':
        res.headers.get('content-disposition') ??
        `attachment; filename="${id}.ass"`,
    },
  });
}
