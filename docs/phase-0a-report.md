# Phase 0A report — repository discovery and architecture decisions

Date: 2026-07-24

## Summary

GSWGuard is scoped as a dedicated monorepo under `GSWGuard/`. The existing Playground root is not a Git repository and contains unrelated projects, so no sibling project was modified. This execution created only architecture and planning documentation, as required by the amendment.

## Environment

- Host: macOS (Darwin; exact host build not needed for this phase).
- Git: 2.39.5.
- Node.js: v25.8.2; npm 11.11.1.
- Python: 3.14.3.
- Docker: 29.5.2; daemon availability was not required for documentation-only work.
- `dotnet`: not installed; C# compilation and Windows APIs cannot be validated locally.
- Windows 11, DPAPI, Event Log, service packaging, Authenticode, Winget, and Windows integration: unavailable locally; require `windows-latest` CI and a dedicated Windows 11 environment.
- GitHub remote, repository ownership, branch protection, and credentials: not discoverable from this workspace.

## Decisions recorded

Monorepo boundary, OpenAPI contracts, PostgreSQL jobs/outbox, and Windows CI strategy are recorded in ADRs 0001–0004. Main trust boundaries and data-minimization boundaries are recorded in `docs/architecture/trust-boundaries.md`. Traffic assumptions are recorded in `docs/architecture/scaling.md`.

## Highest-risk capabilities

1. Privileged LocalSystem agent execution and update trust.
2. Enrollment credentials, replay protection, and organization isolation.
3. Software/package execution, installer tampering, signatures, hashes, and silent arguments.
4. Approved-folder file operations, including traversal and reparse points.
5. Supabase/Auth/RLS correctness and bootstrap-account security.
6. Reliable job claiming, idempotency, expiry, and audit integrity.
7. Session 0/user-session notification behavior.
8. External Google Drive and email-provider credentials and failure modes.

## Deferred decisions

- Exact GitHub repository/remote and whether to initialize Git before Phase 1A; owner action, before 1A.
- Pinned framework, generator, migration, and lint dependency versions; resolve during 1A/1C after current-stable verification.
- C# generated client versus hand-written DTOs with fixture validation; resolve in 1C.
- Supabase region, service-role boundaries, RLS details, retention, and bootstrap mechanism; resolve in Phase 2.
- Production code-signing certificate, publisher identity, storage, rotation, and emergency rollback; ADR before production self-update.
- Google Shared Drive configuration versus OAuth fallback; deployment decision before Phase 8.
- Backend streaming versus constrained download mechanism; ADR immediately before Phase 8.
- Package limits, allowed installer formats/manifests, Winget policy, and notification-helper implementation; resolve in Phases 6/8.
- Compliance policy defaults, auto-remediation rules, and retention/export formats; resolve in Phases 7/10.
- DigitalOcean sizing, database indexes/worker cadence, and Redis introduction; measure in Phase 11.

## Validation performed

Repository discovery and tool-version checks completed. Documentation has not yet been linted because no project tooling exists in this Phase 0A-only repository. No application build or tests were run; no application exists by design.

## Files changed

- `docs/adr/0000-adr-index.md`
- `docs/adr/0001-monorepo-structure.md`
- `docs/adr/0002-contracts-source-of-truth.md`
- `docs/adr/0003-postgresql-jobs-and-event-outbox.md`
- `docs/adr/0004-windows-build-and-validation.md`
- `docs/architecture/trust-boundaries.md`
- `docs/architecture/scaling.md`
- `docs/implementation-plan.md`
- `docs/phase-0a-report.md`

## Recommended next execution

Phase 0B: create the baseline security foundation and threat model only, then stop for review. Phase 1A must not begin until Phase 0B is approved.
