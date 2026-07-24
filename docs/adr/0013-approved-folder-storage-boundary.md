# ADR 0013: Approved-folder storage boundary

- Status: Proposed for Phase 9 review
- Date: 2026-07-24

## Context

Remote file operations can expose personal data or enable path traversal if they accept raw local paths or provider URLs. GSWGuard’s product boundary allows only centrally approved company folders.

## Decision

Represent folders and files with organization-scoped opaque IDs. The API authorizes every operation against an approved-folder policy and job; the agent never supplies authority through a raw path or URL. The server performs canonical path and reparse-point checks, applies extension/size limits, streams bytes, records metadata-only audit events, and defaults deletion to quarantine/soft-delete where supported. File contents are never collected during inventory, logged, rendered, or executed.

## Consequences

This limits surveillance and traversal risk but requires explicit folder configuration and provider adapters. Operations are more auditable than arbitrary file commands. Malware scanning, permanent deletion, and general filesystem browsing are not included in the prototype.
