# GSWGuard trust boundaries (Phase 0A)

1. **Administrator browser → dashboard/API**: authenticated Supabase session/JWT crosses an internet boundary. API authorization, organization scoping, CSRF/session rules, rate limits, and audit logging are mandatory; UI visibility is not authorization.
2. **Dashboard/API → Supabase PostgreSQL/Auth**: backend service credentials and user claims cross a provider boundary. Service-role use must stay server-side; RLS and organization IDs provide defense in depth.
3. **API → Windows agent**: untrusted internet transport to a privileged LocalSystem process. HTTPS, per-device credentials, timestamps/replay protection, idempotency, schema validation, size limits, leases, and credential revocation apply.
4. **API → Google Drive**: external storage boundary. Only Drive IDs/metadata enter PostgreSQL; credentials remain server-side. Package replacement, deletion, movement, permissions, Shared Drive behavior, and checksums are threat-modeled before Phase 8.
5. **API → Resend**: external email boundary. Send only sanitized, deduplicated notification content; provider failures are retryable and audited without secrets.
6. **Agent LocalSystem → Windows OS and user session**: privileged boundary. No arbitrary shell/scripts; predefined versioned handlers, bounded timeouts, DPAPI, signed updates, and an authenticated user-session notification helper are required. Session 0 isolation is a design constraint.
7. **Agent → approved company-folder storage**: file-content boundary. Path validation, reparse-point defenses, allowlisted folders/extensions, size limits, quarantine/deletion policy, and audit correlation are required before Phase 9.
8. **CI/GitHub → build artifacts**: supply-chain boundary. Secrets are unavailable to untrusted PRs; dependencies are scanned; production signing keys never enter ordinary PR workflows.

## Data minimization boundary

The system must not collect passwords, tokens, keystrokes, webcam/microphone data, screenshots, browser history, email/chat content, document contents during inventory, precise location, or personal files outside explicitly approved company folders.
