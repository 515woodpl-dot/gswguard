import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic';

export function GET() {
  return NextResponse.json(
    {
      supabaseUrl: process.env.SUPABASE_URL ?? '',
      supabaseAnonKey: process.env.SUPABASE_ANON_KEY ?? '',
      apiBaseUrl: process.env.API_BASE_URL ?? 'http://localhost:8000',
    },
    { headers: { 'Cache-Control': 'no-store' } },
  );
}
