# Software deployment threat model

- Scope: Phase 8 gate
- Date: 2026-07-24
- Status: Review required before implementation

## Assets and trust boundaries

- Approved package manifests, package IDs, versions, hashes, signatures, installer arguments, and rollout state.
- Google service-account credentials, Shared Drive IDs, package files, and Drive permissions.
- API authorization decisions, package bytes, agent download cache, and Windows execution context.
- The package catalog is trusted only when changed by an authorized Owner/Administrator and audited. Google Drive is an external storage boundary; a Drive file ID or URL is not proof of package integrity.
- The Windows agent is privileged, so package execution can affect the entire device. A package publisher, Winget source, installer, archive, or manifest is untrusted until all policy checks pass.

## Threats and required controls

| Threat | Required control | Validation |
| --- | --- | --- |
| Stolen Google service-account key | Server-only secret storage, minimum Shared Drive permission, rotation/revocation runbook, no agent exposure | Deployment/Phase 11 |
| Drive file replacement under same ID | Store expected SHA-256 and size; verify bytes every download; verify package version metadata; fail closed | Package tests |
| File moved/deleted/permission changed | Resolve expected Shared Drive/file ID; require `supportsAllDrives`; fail closed and audit provider error | Provider tests |
| Malicious package catalog entry | Owner/Administrator authorization, immutable audit, schema validation, allowlisted source/format, approval state | API/RLS tests |
| Compromised or spoofed Winget source | Pin package ID/version/source where possible; verify installed result and expected version; do not treat search results as approval | Windows integration |
| MSI custom action or EXE arbitrary behavior | Approved package manifest; allowlisted executable type; no user-supplied command line; bounded safe arguments; signature/hash checks | Manifest tests/Windows VM |
| ZIP path traversal or reparse point | Extract to isolated temporary directory; reject absolute paths, `..`, symlinks, junctions, reparse points, oversized entries, and archive bombs | Windows security tests |
| Silent-install argument injection | Arguments represented as typed fields, not shell strings; reject metacharacters and unsupported switches; package-specific allowlist | Manifest tests |
| Unsigned or wrong-publisher installer | Require Authenticode for formats that support it; pin trusted publisher certificate identity; reject expired/invalid/mismatched signatures | Windows signature tests |
| Hash collision/mismatch or partial download | Stream with bounded size/timeouts; compute SHA-256 while downloading; require exact expected length/hash; delete failed cache | Download tests |
| Replay/downgrade | Package/version state, job expiry/idempotency, reject downgrade unless explicit rollback policy and audit reason | Job/package tests |
| Download authorization bypass | Authorize organization, device, job, package, version, and approval before bytes are sent; never hand agent a permanent Drive URL | API tests |
| Package content leaks | Do not log bytes or secrets; restrict cache permissions; delete/quarantine according to policy; audit metadata only | Agent tests |
| Installer reboots unexpectedly | Require manifest reboot policy; default no automatic reboot; employee notification and grace period for disruptive actions | Windows VM |

## Approved package formats

The initial catalog may contain Winget references and approved MSI packages. EXE and ZIP support remains constrained: each requires a package-specific manifest, exact hash, publisher/signature policy, bounded arguments, expected install/uninstall behavior, and a Windows test fixture. Arbitrary EXE/ZIP upload is prohibited.

## Installer trust model

The API authorizes a package job; the agent retrieves bytes through the API, verifies expected size and SHA-256, verifies Authenticode where required, validates the manifest, and invokes only a versioned handler. A successful HTTP response, Drive file ID, filename, or installer exit code alone is insufficient. The agent reports sanitized structured results and does not send package content to the server.

## Google Drive model

Production prefers a Google Workspace Shared Drive with a dedicated GSWGuard folder and minimum service-account access. Store only Drive IDs and package metadata in PostgreSQL. If Shared Drive access is unavailable, stop for owner approval of OAuth company-account storage or another provider; do not silently fall back to service-account-owned My Drive uploads.

## Validation plan

- Unit-test manifest schema, typed arguments, hash/size verification, archive path checks, downgrade rules, and failure-closed behavior.
- Fake Google Drive tests cover replacement, move, delete, permission loss, partial reads, timeout, and Shared Drive query flags.
- Windows CI tests signature verification using generated test certificates, including valid, invalid, expired, wrong-publisher, and unsigned cases.
- A dedicated Windows 11 VM tests Winget/MSI/EXE/ZIP behavior without destructive system-policy changes.
- Production self-update and signing remain unavailable until the signing ADR and certificate workflow are accepted.

## Explicit non-goals

No arbitrary shell/PowerShell execution, user-provided scripts, unsupervised package uploads, automatic reboot after installation, permanent public package URLs, or malware scanning claims are allowed in the prototype.
