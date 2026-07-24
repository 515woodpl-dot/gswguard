import type { HealthResponse } from '@gswguard/contracts/generated/typescript/health';

export function GET(): Response {
  const body: HealthResponse = {
    status: 'healthy',
    service: 'gswguard-dashboard',
    version: '0.1.0',
    checked_at: new Date().toISOString(),
    request_id: '00000000-0000-0000-0000-000000000000',
  };
  return Response.json(body);
}
