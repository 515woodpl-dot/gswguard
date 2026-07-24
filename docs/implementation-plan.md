# GSWGuard phased implementation plan

This plan follows the supplied amendment and final addendum. Each execution unit stops at its review gate; the owner’s explicit “approved”, “continue”, or equivalent response authorizes the next unit.

| Unit | Bounded objective | Exit evidence |
| --- | --- | --- |
| 0A | Discovery, trust boundaries, ADRs, deferred decisions | Documentation review; no app code |
| 0B | Baseline threat model and security foundation | Threat-model review; phase-specific placeholders |
| 1A | Monorepo tooling, docs, ignore/env conventions, CI skeleton | Tooling/YAML/docs validation |
| 1C | One OpenAPI/JSON Schema contract through Python, TypeScript, and C# | Fixtures, generation/drift tests, C# strategy ADR |
| 1B | Minimal dashboard/API/agent skeletons using accepted contracts | Builds, lint/type/test; Windows limitations reported |
| 2 | Supabase schema, auth, roles, bootstrap, RLS | Migration and authorization tests |
| 3 | Enrollment, credentials, heartbeat, online/offline state | Race/replay/credential tests |
| 4 | Normalized hardware/security inventory | Agent fakes, API, dashboard tests |
| 5 | Software scans and change history | 15-minute scheduler and correlation tests |
| 6 | PostgreSQL jobs, actions, leases, results, notifications | Idempotency/expiry/authorization tests |
| 7 | Compliance rules, evidence, scoring, remediation | Policy and loop-prevention tests |
| 8 | Installer threat model, Google Drive packages, signed/hash-checked deployment | Threat-model approval, package safety tests, download-transport ADR |
| 9 | Approved-folder threat model and safe file operations | Path/reparse/size/authorization tests |
| 10 | Resend, immutable audit, timeline, exports, retention | Export and integrity tests |
| 11 | DigitalOcean/Supabase deployment and hardening | Windows 11 test plan, smoke tests, recovery/security review |

## Phase 1B review gate

Stop after each execution unit. The next execution requires explicit owner approval. Application skeletons may be built in Phase 1B, but no business features, database migrations, authentication, enrollment, or privileged management behavior belong in this phase.
