# Phase 0B report — baseline security foundation

## Implemented

- Added the project security policy and reporting boundary in `SECURITY.md`.
- Added a baseline cross-system threat model covering authentication, organization isolation, enrollment tokens, device credentials, replay, audit integrity, secrets, CI, dependencies, and administrator compromise.
- Added explicit phase gates for the software-deployment and approved-folder file-operation threat models.

## Validation

- Confirmed the new security documents are non-empty.
- Confirmed no application, database, CI, or privileged-agent implementation was created in Phase 0B.
- No build, application tests, or Windows tests were run because this unit is documentation-only.

## Remaining risks

The baseline controls are design requirements, not evidence of implemented security. Supabase RLS, token races, replay protection, audit storage, CI secret scanning, and Windows-specific controls require implementation and tests in later phases.

## Deferred decisions

- Exact authentication/bootstrap implementation and RLS policies: Phase 2.
- Device credential and replay protocol details: Phase 3.
- Job-level authorization/idempotency: Phase 6.
- Production signing/update trust: before production self-update and Phase 11.
- Software deployment threat model: immediately before Phase 8.
- Approved-folder file-operation threat model: immediately before Phase 9.

## Review gate

Stop after Phase 0B. Explicit owner approval is required before beginning Phase 1A.
