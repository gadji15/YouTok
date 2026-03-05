import { NextResponse } from 'next/server';

import { laravelInternalFetch } from '@/lib/server/laravel';

export async function GET() {
  const res = await laravelInternalFetch('/api/tiktok-accounts');

  const contentType = res.headers.get('content-type') ?? 'application/json; charset=utf-8';
  const body = await res.text();

  return new NextResponse(body, {
    status: res.status,
    headers: { 'Content-Type': contentType },
  });
}
