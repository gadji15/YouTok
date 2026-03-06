import { NextResponse, type NextRequest } from 'next/server';

import { laravelInternalFetch } from '@/lib/server/laravel';

export async function POST(req: NextRequest) {
  const formData = await req.formData();

  const res = await laravelInternalFetch('/api/uploads/video', {
    method: 'POST',
    body: formData,
  });

  const json = await res.json();
  return NextResponse.json(json, { status: res.status });
}
