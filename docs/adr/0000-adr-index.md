# GSWGuard Architecture Decision Records

Status values: `Proposed`, `Accepted`, `Superseded`, or `Rejected`. Material changes must create a new ADR and link both records; accepted ADRs are historical records.

| ID | Decision | Status |
| --- | --- | --- |
| [0001](0001-monorepo-structure.md) | Monorepo boundaries and repository location | Proposed |
| [0002](0002-contracts-source-of-truth.md) | FastAPI OpenAPI as HTTP contract source of truth | Proposed |
| [0003](0003-postgresql-jobs-and-event-outbox.md) | PostgreSQL-backed jobs and transactional event outbox | Proposed |
| [0004](0004-windows-build-and-validation.md) | Windows-specific build and validation strategy | Proposed |
| 0005 | Agent update signing and trust model | Deferred to Phase 1B/11 |
| 0006 | Session 0 notification architecture | Deferred to Phase 6 |
| [0010](0010-csharp-contract-validation.md) | C# compatibility validation for Phase 1C | Accepted for Phase 1C |
| 0007 | Package-download transport | Required immediately before Phase 8 |
| 0008 | Software-deployment threat model and installer trust | Required immediately before Phase 8 |
| 0009 | Approved-folder file-operation threat model | Required immediately before Phase 9 |
| [0011](0011-package-download-transport.md) | Backend-mediated package download transport | Proposed for Phase 8 review |
| [0012](0012-installer-trust-and-signing.md) | Installer trust and signing gate | Proposed for Phase 8 review |
| [0013](0013-approved-folder-storage-boundary.md) | Approved-folder storage boundary | Proposed for Phase 9 review |

## Deferred decisions

The following are intentionally not selected in Phase 0A: Supabase project/region and retention settings; exact API hosting sizing; Google Shared Drive versus OAuth fallback; Resend sender/domain; package size limits; refresh-token implementation details; compliance-policy defaults; production code-signing authority; notification helper implementation; schema generator versions; database migration tooling; and whether a later fleet requires Redis. Each is resolved in the phase listed in the implementation plan or before the affected integration.
