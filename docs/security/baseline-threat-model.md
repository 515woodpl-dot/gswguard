# Baseline security threat model

- Scope: Phase 0B cross-system foundation
- Date: 2026-07-24
- Status: Baseline; implementation-specific details remain phase-gated

## Assets

1. Organization membership, roles, policies, device records, inventory, jobs, audit records, and timelines.
2. Enrollment tokens and per-device credentials.
3. Supabase Auth sessions/JWTs and server-side provider credentials.
4. Windows agent binaries, configuration, local DPAPI-protected secrets, and action results.
5. Installer/package metadata and approved company-folder metadata.
6. Availability, integrity, and confidentiality of management operations.

## Actors and trust assumptions

- Owner, Administrator, and Viewer accounts may be compromised; authorization must limit impact.
- A device user may be a standard user, but a local administrator can ultimately stop/remove software; GSWGuard must detect and report tampering rather than claim immutability.
- The dashboard browser, internet, DNS, Google Drive, Resend, GitHub Actions, and hosted infrastructure are not automatically trusted.
- Supabase Auth and PostgreSQL provide configured provider guarantees, but application authorization and RLS must be independently tested.
- The agent runs privileged and is a high-impact target; server commands and payloads are untrusted until validated.

## Threats and baseline controls

| Threat | Impact | Required baseline control | Validation phase |
| --- | --- | --- | --- |
| Stolen dashboard session/JWT | Unauthorized management or data access | JWT validation, server-side role/org checks, expiry/refresh rules, logout-all support, rate limiting, audit | 2 |
| Public self-registration or first-user takeover | Rogue Owner | No public signup; explicit one-time bootstrap secret/allowlist; idempotent and audited bootstrap disabled after use | 2 |
| Cross-organization identifier guessing | Data disclosure or action against another tenant | Organization ID on domain rows, authorization at service boundary, Supabase RLS, negative tests | 2 |
| Enrollment token theft | Rogue device enrollment | High-entropy single-use short-lived token, store only hash, atomic consume, TLS, label/audit/notification, no token logs | 3 |
| Enrollment replay/race | Duplicate device or credential | Transactional token consumption, unique constraints, idempotency key, replay rejection | 3 |
| Device credential theft | Agent impersonation | Per-device credential, revocation status, secure rotation interface, DPAPI local protection, never return credential after initial enrollment | 3 |
| Request replay | Repeated restart/delete/install | Timestamp plus bounded clock drift, nonce/idempotency key, server-side replay record, expiry, action-specific idempotency | 3/6 |
| Malformed or oversized payload | Resource exhaustion or parser abuse | Strict schemas, request-size limits, bounded decompression, rate limits, correlation IDs, sanitized errors | 1B/3 |
| Job double execution | Disruptive duplicate action | Atomic lease claims, idempotency keys, expiry, max attempts, state machine, result deduplication | 6 |
| Audit alteration or deletion | Loss of accountability | Append-only application model, restricted database writes, actor/correlation/outcome fields, integrity tests, export controls | 2/10 |
| Secret leakage in source/CI/logs | Account or infrastructure compromise | Secret scanning, least-privilege CI, masked logs, no production secrets in PR workflows, provider rotation runbook | 1A/11 |
| Dependency or action-handler compromise | Remote code execution or data loss | Pinned/reviewed dependencies, scanning, small typed handlers, no arbitrary commands, signed production updates, staged release | 1A/6/11 |
| Administrator account compromise | Fleet-wide impact | Least privilege, Viewer role, confirmation/reason fields, audit, notification, future MFA design, recovery/bootstrap controls | 2/10 |
| Service tampering/uninstall | Loss of management coverage | Windows service recovery, Event Log, tamper events/alerts, controlled uninstall code, honest LocalSystem limitations | 1B/3/11 |

## Authentication and authorization boundary

Supabase Auth authenticates human users. The API validates JWT signature, issuer, audience, expiry, and claims, then resolves an organization-scoped profile and role. Every mutation independently checks role and target organization. Viewer is read-only. Device authentication is separate from human authentication and cannot be substituted with a user JWT.

The dashboard may hide unavailable controls for usability, but the API must reject unauthorized requests. Service-role credentials, Google credentials, Resend credentials, signing identities, and bootstrap secrets remain backend/deployment secrets and never enter browser or agent storage.

## Organization isolation

Every tenant-owned row carries an organization identifier, including devices, jobs, packages, folders, policies, notifications, audit entries, and timeline records. Services derive scope from authenticated context rather than trusting arbitrary client-supplied organization IDs. RLS policies deny cross-tenant access, and tests cover both direct table access and API paths. Background workers preserve organization scope when processing outbox events.

The dashboard receives the Supabase anon key at runtime; this key is public by design. Direct-to-Postgres tenant isolation therefore rests on Supabase RLS. Every tenant-owned table must have RLS enabled with organization-scoped policies, or an intentional deny-all policy where only server-side functions write. Adding a table without an RLS policy is a release-blocking regression.

## Enrollment and device identity

Enrollment is a one-time bootstrap exchange over HTTPS. The server stores a hash of a random short-lived token, consumes it atomically, creates a unique device identity and credential, returns the credential only once, and records audit/notification events. Device identity uniqueness, credential status, revocation, enrollment time, and future rotation timestamps are modeled. Enrollment endpoints are rate-limited and reject reused, expired, malformed, or organization-mismatched requests.

## Replay, idempotency, and time

Requests that can mutate state carry a server-validated timestamp and idempotency key. The API rejects old timestamps outside a configured drift window and records consumed nonces/keys for the relevant scope and retention period. Retries return the original result when safe. Job expiration, lease expiration, and device credential revocation are checked before execution.

## Audit integrity

Security-relevant actions emit audit data in the same transaction as the state mutation or through a transactional outbox. Records include event ID, organization, actor type/ID, device/job target, action, reason where required, correlation/request ID, timestamp, outcome, and sanitized error code. No secret, token, file content, or sensitive payload is recorded. Physical database superusers/provider operators are outside the application’s control and are addressed in deployment/recovery documentation.

## Secret handling and CI

`.env` files, service-account keys, signing keys, bootstrap secrets, and device credentials are local/deployment-only. `.env.example` contains names and safe placeholders only. CI pull requests run without production secrets; secret scanning, dependency review, and CodeQL run before merge. Logs are structured and redacted. Rotation and incident response are required before production deployment.

## Testing-mode hardening

- API and dashboard containers run as non-root users.
- Production rejects empty or wildcard credentialed CORS origins.
- API responses include restrictive JSON/API security headers.
- The in-process limiter is only a small-instance abuse brake. It ignores `X-Forwarded-For` unless the exact trusted proxy count is configured.
- Membership infrastructure failures return HTTP 503 rather than silently changing authorization behavior.

## Deferred phase-specific threat models

The following are explicit gates and must be created/reviewed before implementation:

- **Before Phase 8:** software deployment threat model covering Google Drive replacement/tampering, Shared Drive permissions, backend streaming versus constrained delivery, Winget/MSI/EXE/ZIP execution, signatures, SHA-256, package manifests, silent-install arguments, rollback, and service-account compromise.
- **Before Phase 9:** approved-folder file-operation threat model covering traversal, reparse points, symlinks/junctions, unauthorized downloads, quarantine/deletion, file-size/extension abuse, malware handling, and content boundaries.

Those capabilities must not be represented as implemented by a placeholder security check.
