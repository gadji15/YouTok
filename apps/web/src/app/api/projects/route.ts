import { NextResponse } from 'next/server';

import { laravelInternalFetch } from '@/lib/server/laravel';

export async function GET() {
  const res = await laravelInternalFetch('/api/projects');
  const json = await res.json();
  return NextResponse.json(json, { status: res.status });
}

export async function POST(req: Request) {
  const body = await req.json();

  const res = await laravelInternalFetch('/api/projects', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  const json = await res.json();
  return NextResponse.json(json, { status: res.status });
}
