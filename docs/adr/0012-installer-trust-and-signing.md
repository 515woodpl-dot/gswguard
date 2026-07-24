# ADR 0012: Installer trust and signing gate

- Status: Proposed for Phase 8 review
- Date: 2026-07-24

## Context

GSWGuard must distinguish approved package metadata from trustworthy executable bytes. MSI/EXE/ZIP and Winget behavior have different publisher, signature, archive, and argument risks.

## Decision

Treat package manifests, exact SHA-256, expected size, package/version approval, and format-specific validation as mandatory. Authenticode verification is required where the package policy says it is supported. Trusted publisher identity, certificate expiry/revocation, rollback, and production agent update signing must be decided and tested before production deployment. Unsigned development fixtures may be used only in explicit development tests and never through a remotely supplied job.

No package handler may accept arbitrary command strings. Handlers receive typed, allowlisted arguments and bounded timeouts. A missing or invalid signature/hash/manifest fails closed.

## Consequences

Package rollout is slower to configure but auditable and resistant to Drive replacement and argument injection. Production self-update and package execution remain unavailable until signing identities and Windows fixtures exist.
