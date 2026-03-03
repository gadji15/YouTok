import { laravelInternalFetch } from '@/lib/server/laravel';

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id?: string }> }
) {
  const { id } = await params;
  if (!id) {
    return new Response('Missing project id.', { status: 400 });
  }

  const res = await laravelInternalFetch(
    `/api/projects/${encodeURIComponent(id)}/artifacts/transcript`
  );

  return new Response(res.body, {
    status: res.status,
    headers: {
      'content-type': res.headers.get('content-type') ?? 'application/json',
      'content-disposition':
        res.headers.get('content-disposition') ??
        'attachment; filename="transcript.json"',
    },
  });
}
