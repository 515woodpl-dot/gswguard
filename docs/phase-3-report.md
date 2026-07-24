# Phase 3 report — enrollment and device identity

## Implemented

- Added device and enrollment-token Supabase tables with expiry, single-use consumption, credential hash, revocation, heartbeat, and organization scope fields.
- Added RLS policies and pgTAP checks for device/token access boundaries.
- Added thread-safe enrollment service proof with high-entropy tokens, SHA-256-at-rest hashes, atomic token consumption, one-time device credential return, credential verification, revocation handling, and heartbeat clock-skew checks.
- Added race, replay, invalid-credential, and heartbeat tests.

## Validation

- API/enrollment tests run locally.
- Python syntax, contract drift, documentation, and CI YAML checks run locally.
- Supabase SQL/pgTAP was not executed because this host has no Supabase CLI, PostgreSQL client, or running database.
- Windows DPAPI storage and agent transport were not implemented or validated in this phase; those are Windows-agent integration work.

## Security notes

- Enrollment and device credentials are never stored in plaintext by the service fake or intended schema.
- A token is removed atomically before enrollment completes in the fake; the production adapter must perform equivalent row-locked transaction behavior.
- Heartbeat credentials are separate from Supabase human JWTs.
- The in-memory store is test-only and must not be used for production persistence.

## Deferred decisions

- Production Postgres adapter and exact transaction/function boundary.
- Windows DPAPI credential storage and agent HTTPS transport.
- Device credential rotation workflow.
- Offline calculation worker and 24-hour offline notification.
- Enrollment dashboard UI and administrator authorization wiring.

## Review gate

Stop after Phase 3. Explicit owner approval is required before Phase 4 implements hardware, Windows, storage, security, and software inventory.
