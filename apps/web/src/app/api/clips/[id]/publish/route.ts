import { NextResponse } from 'next/server';

import { laravelInternalFetch } from '@/lib/server/laravel';

export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  const body = await req.text();

  const res = await laravelInternalFetch(`/api/clips/${encodeURIComponent(id)}/publish`, {
    method: 'POST',
    headers: {
      'content-type': req.headers.get('content-type') ?? 'application/json; charset=utf-8',
    },
    body,
  });

  const contentType = res.headers.get('content-type') ?? 'application/json; charset=utf-8';
  const responseBody = await res.text();

  return new NextResponse(responseBody, {
    status: res.status,
    headers: { 'Content-Type': contentType },
  });
}
