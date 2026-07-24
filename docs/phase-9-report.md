# Phase 9 report — approved-folder file operations

## Implemented

- Added approved-folder, file-object, and file-operation audit schema with RLS.
- Added organization-scoped folder policies for extensions, size, allowed operations, and quarantine.
- Added canonical relative-path validation, traversal/absolute/ADS rejection, root containment, and symlink/reparse-style checks.
- Added bounded streaming upload/download and SHA-256 metadata.
- Added quarantine-first deletion behavior with explicit policy checks.
- Added local provider tests for upload, download, quarantine, traversal, symlink escape, extension abuse, and size limits.

## Validation

- File-operation/API test suite passes locally.
- Contract, documentation, Python syntax, and CI YAML checks pass.
- Supabase SQL/pgTAP was reviewed but not executed locally.
- Windows junction/reparse-point, ACL, alternate-data-stream, and cache tests were not executed on macOS.

## Security notes

- The local provider is for tests/development; production Google Drive/provider adapters must preserve opaque IDs and version checks.
- Raw paths and provider URLs are not authority; folder policy and server-side authorization must be applied by the eventual API layer.
- Permanent deletion is disabled unless policy explicitly allows it and quarantine is enabled.

## Deferred decisions

- Production provider adapter and file-object version/etag semantics.
- Upload/download API authorization and job binding.
- Windows reparse-point/ACL implementation and cache cleanup.
- Malware-scanning provider and incident workflow.

## Review gate

Stop after Phase 9. Explicit owner approval is required before Phase 10 implements notifications, immutable audit search/exports, timeline views, and retention jobs.
