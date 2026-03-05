import { NextResponse } from 'next/server';

import { laravelInternalFetch } from '@/lib/server/laravel';

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id?: string }> }
) {
  const { id } = await params;
  if (!id) {
    return NextResponse.json({ error: 'Missing clip id.' }, { status: 400 });
  }

  const res = await laravelInternalFetch(`/api/clips/${encodeURIComponent(id)}`);
  const json = await res.json();
  return NextResponse.json(json, { status: res.status });
}

export async function PATCH(
  req: Request,
  { params }: { params: Promise<{ id?: string }> }
) {
  const { id } = await params;
  if (!id) {
    return NextResponse.json({ error: 'Missing clip id.' }, { status: 400 });
  }

  const body = await req.text();

  const res = await laravelInternalFetch(`/api/clips/${encodeURIComponent(id)}`, {
    method: 'PATCH',
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

export async function DELETE(
  _req: Request,
  { params }: { params: Promise<{ id?: string }> }
) {
  const { id } = await params;
  if (!id) {
    return NextResponse.json({ error: 'Missing clip id.' }, { status: 400 });
  }

  const res = await laravelInternalFetch(`/api/clips/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  });

  if (res.status === 204) {
    return new NextResponse(null, { status: 204 });
  }

  const contentType = res.headers.get('content-type') ?? 'application/json';
  const responseBody = await res.text();
  return new NextResponse(responseBody, {
    status: res.status,
    headers: { 'Content-Type': contentType },
  });
}
