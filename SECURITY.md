# GSWGuard security

GSWGuard manages company-owned Windows devices and executes a limited set of privileged, predefined actions. Security is part of the product boundary, not a substitute for Windows administration or endpoint protection.

## Reporting a vulnerability

Do not disclose suspected vulnerabilities in public issues. Until an owner-approved security contact is configured, report them privately to the Golden Stone Works project owner with reproduction steps, affected component, impact, and any suggested mitigation. Do not include passwords, tokens, private keys, device credentials, or personal data in a report.

The project is private/proprietary pending an owner license decision. No public security SLA is claimed by this prototype.

## Security commitments

- Every organization-scoped read and write is authorized server-side; dashboard controls are not a security boundary.
- Device credentials, enrollment tokens, provider credentials, and production signing keys are never logged or committed.
- The agent never accepts arbitrary shell, PowerShell, Python, or user-supplied scripts.
- Sensitive actions are typed, confirmed, audited, bounded, and expiring.
- Audit records are append-only from the application’s perspective and include actor, organization, device/job scope, correlation, outcome, and timestamps.
- Inventory follows documented data minimization; passwords, browser credentials, keystrokes, recordings, screenshots, browsing history, message content, precise location, and unapproved personal files are not collected.

## Scope and limitations

The baseline threat model is in [`docs/security/baseline-threat-model.md`](docs/security/baseline-threat-model.md). Software deployment and approved-folder file operations are intentionally not fully threat-modeled yet. They are gated by phase-specific threat models before implementation.
