import { NextResponse, type NextRequest } from 'next/server';

import { laravelInternalFetch } from '@/lib/server/laravel';

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id?: string }> }
) {
  const { id } = await params;
  if (!id) {
    return NextResponse.json({ error: 'Missing project id.' }, { status: 400 });
  }

  const res = await laravelInternalFetch(`/api/projects/${encodeURIComponent(id)}/debug`);
  const contentType = res.headers.get('content-type') ?? 'application/json';
  const body = await res.text();
  return new NextResponse(body, { status: res.status, headers: { 'Content-Type': contentType } });
}
