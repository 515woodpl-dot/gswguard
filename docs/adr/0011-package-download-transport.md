# ADR 0011: Package-download transport for the initial deployment

- Status: Proposed for Phase 8 review
- Date: 2026-07-24

## Context

GSWGuard stores approved installer files in Google Drive and must authorize package delivery per organization, device, job, package, and version. Google Drive does not provide the same conventional object-storage signed URL model as a dedicated object store. The initial fleet is two devices and package sizes are expected to be small enough for a backend-mediated path, but DigitalOcean request limits and interrupted downloads must be validated.

## Options considered

### Option A — stream through FastAPI

The backend keeps Drive credentials server-side, authorizes the job, streams bytes without buffering the whole file, enforces size/time limits, correlates audit, and requires agent-side SHA-256 verification.

### Option B — constrained short-lived delivery

A proxy or temporary token mechanism avoids application bandwidth but adds expiration, replay prevention, audit correlation, and Google Drive delivery complexity. Google Drive is not assumed to issue a conventional signed URL.

## Decision

Use backend-mediated streaming as the prototype default, subject to a Phase 8 delivery test. The implementation must stream, not buffer; enforce authorization before transfer; support cancellation/timeouts; enforce maximum size; validate expected Drive file ID/version metadata; avoid logging content; record transfer outcome; and require agent-side exact size/SHA-256 validation before execution.

If DigitalOcean request-duration or bandwidth limits make this unreliable for approved package sizes, create a superseding ADR before changing transport. Do not silently switch to public or long-lived Drive URLs.

## Consequences

Credentials and authorization remain centralized and audit correlation is straightforward. The API carries package bandwidth and must handle retries/ranges where practical. The maximum package size and range behavior are deferred until provider tests and deployment limits are measured.
