import { NextResponse } from 'next/server';

import { laravelInternalFetch } from '@/lib/server/laravel';

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const res = await laravelInternalFetch(`/api/projects/${encodeURIComponent(id)}`);
  const json = await res.json();
  return NextResponse.json(json, { status: res.status });
}
