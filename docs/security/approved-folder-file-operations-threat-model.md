# Approved-folder file-operation threat model

- Scope: Phase 9 gate
- Date: 2026-07-24
- Status: Review required before implementation

## Boundary and assets

GSWGuard may exchange files only through centrally configured company folders. The API/database stores organization, folder, provider-object, and audit metadata; file bytes remain behind the approved storage boundary. A Windows agent is an untrusted client even though it runs as LocalSystem, and a signed-in employee may have access to the device filesystem outside the approved folder.

Personal folders, arbitrary paths, whole-drive scans, document contents, and general remote file browsing are outside scope.

## Threats and required controls

| Threat | Required control | Validation |
| --- | --- | --- |
| `..` traversal or absolute path | Resolve against configured canonical root; reject absolute/parent paths before and after resolution | Unit/Windows tests |
| Symlink, junction, or reparse-point escape | Reject reparse points at every path component; open handles with no-follow semantics where available; revalidate before transfer | Windows VM |
| Case/Unicode normalization bypass | Canonicalize with Windows comparison rules; reject ambiguous names; test case and normalization variants | Windows tests |
| Unauthorized folder/device access | Authorize organization, approved-folder ID, device, action, and actor/job before bytes transfer | API tests |
| Arbitrary download URL | Never accept agent-provided URLs or Drive URLs; use opaque folder/file IDs resolved server-side | API tests |
| Extension spoofing | Allowlist extensions per folder policy; inspect filename and content type; do not claim malware detection | Validation tests |
| Oversized file or archive bomb | Enforce per-file, per-request, and aggregate limits before persistence; stream; reject excessive compression ratio/entry count | Unit/stream tests |
| Malware upload | Store/quarantine according to explicit policy; do not execute or preview; integrate a scanner only as a separately approved capability | Operations/Phase 10 |
| Delete abuse | Require confirmation and reason; authorize exact file ID/path; soft-delete/quarantine first where provider supports it; audit outcome | API/provider tests |
| Download data leak | Stream only after authorization; no content in logs; short-lived job binding; audit start/end/failure | API/provider tests |
| Concurrent replacement | Use provider file ID/version/etag where available; verify metadata before and during transfer; fail on change | Provider tests |
| Storage provider permission drift | Fail closed on missing/moved/deleted objects and permission errors; alert administrators without exposing credentials | Provider tests |
| Local cache exposure | Restrict cache ACL; bounded lifetime; remove on success/failure according to policy; never persist credentials with file | Windows tests |

## Folder policy

Each approved folder must define an organization-scoped ID, provider/root ID, display name, allowed operations, allowed extensions, maximum file size, retention/quarantine behavior, and whether employee-visible notifications are required. A policy change is audited and does not retroactively authorize existing jobs.

## Safe path algorithm

1. Resolve the opaque approved-folder ID server-side and confirm organization scope.
2. Normalize the relative path using platform-specific rules and reject empty, absolute, parent, device, alternate-data-stream, and ambiguous components.
3. Join to the configured root and verify the resulting path remains within the root using canonical comparison.
4. Inspect every existing component for symlink/junction/reparse-point behavior.
5. Recheck authorization, file ID/version, size, and extension immediately before transfer or deletion.
6. Stream through bounded buffers; audit only metadata and outcome.

The agent must not accept a raw local path or provider URL as authority. The server supplies a typed operation bound to an approved folder, opaque object ID, and job ID.

## Quarantine and deletion

The prototype defaults to quarantine/soft-delete where the provider supports it. Permanent deletion requires explicit confirmation, reason, authorization, and an audit record. If quarantine cannot be guaranteed, deletion is disabled until an owner-approved recovery policy exists.

## Malware boundary

GSWGuard is not an antivirus engine and must not label a file safe merely because its extension, hash, or provider metadata is valid. Files are not executed, rendered, indexed for content, or inspected beyond metadata/required safety checks. Malware scanning and incident response are separate operational capabilities.

## Validation plan

- Unit-test path normalization, traversal, reparse-point rejection, Unicode/case variants, extension/size limits, and opaque-ID authorization.
- Provider fakes cover moved/deleted/replaced files, permission loss, changed version/etag, partial transfer, timeout, and delete/quarantine failure.
- Windows 11 VM tests cover NTFS junctions, symlinks, reparse points, alternate data streams, ACLs, and cache cleanup.
- Security tests prove no file bytes, credentials, or raw paths enter structured logs.
