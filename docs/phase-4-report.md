# Phase 4 report — inventory foundation

## Implemented

- Added normalized inventory Pydantic models for Windows, hardware, storage, network, security posture, local-account type/admin status, agent health, and installed software.
- Added stable snapshot canonicalization and SHA-256 hashing.
- Added software add/remove/version-change detection.
- Added PostgreSQL snapshot, current software, software-change history, indexes, and RLS migration.
- Added privacy test rejecting unapproved surveillance fields such as browser history.

## Validation

- API/inventory test suite passes locally.
- Contract, documentation, Python syntax, and CI YAML checks pass.
- Supabase SQL/pgTAP was reviewed but not executed locally because PostgreSQL/Supabase tooling is unavailable.
- Windows WMI, Defender, BitLocker, Secure Boot, TPM, and service integration were not executed on macOS.

## Security/privacy notes

- Inventory models intentionally exclude passwords, tokens, browser history, screenshots, audio/video, document content, precise location, and unapproved personal files.
- Local-account inventory records account name/type/admin status only.
- Snapshot hashes prevent duplicate meaningful snapshots; software changes are normalized by publisher/name.

## Deferred decisions

- Windows-native collector implementation and capability detection.
- Agent-to-API inventory submission and compression/size limits.
- Snapshot retention policy and database pruning job.
- Correlation of software changes with GSWGuard jobs versus manual/Windows Update changes.
- Dashboard device-detail inventory views.

## Review gate

Stop after Phase 4. Explicit owner approval is required before Phase 5 implements continuous software monitoring and notifications.
