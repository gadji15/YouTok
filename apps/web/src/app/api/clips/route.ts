import { NextResponse, type NextRequest } from 'next/server';

import { laravelInternalFetch } from '@/lib/server/laravel';

export async function GET(_req: NextRequest) {
  const res = await laravelInternalFetch('/api/clips');
  const json = await res.json();
  return NextResponse.json(json, { status: res.status });
}
