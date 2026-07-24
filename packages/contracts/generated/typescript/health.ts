// GENERATED FILE. DO NOT EDIT. Source: packages/contracts/poc/source.py
export type HealthStatus = 'healthy' | 'degraded';

export interface HealthResponse {
  status: HealthStatus;
  service: string;
  version: string;
  checked_at: string;
  request_id: string;
  detail?: string | null;
}

export interface ApiError {
  code: string;
  message: string;
  request_id: string;
  details?: Record<string, unknown> | null;
}
