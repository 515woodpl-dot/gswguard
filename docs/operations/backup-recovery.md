# Backup and recovery runbook

## Scope

Supabase PostgreSQL is the system of record for organizations, memberships, devices, jobs, audit records, policy/evaluation history, package metadata, and approved-folder metadata. Google Drive owns package/file bytes according to the approved provider configuration.

## Required controls

- Enable and verify Supabase backups and point-in-time recovery according to the selected plan.
- Export migration files and configuration metadata to the private repository; never export secrets.
- Record Google Shared Drive IDs, file IDs, versions, and permission ownership without copying credentials.
- Test restoration to a non-production project before a production restore.
- Preserve audit records and retention/legal-hold settings during recovery.

## Recovery sequence

1. Declare incident and freeze destructive jobs/actions.
2. Preserve logs, audit exports, provider metadata, and current deployment version.
3. Restore Supabase to an isolated project/time point and validate migrations, RLS, owner access, and audit integrity.
4. Validate package/file provider permissions and expected hashes/versions.
5. Deploy API/dashboard against the restored project with rotated secrets if compromise is suspected.
6. Revoke compromised device credentials and re-enroll only after owner approval.
7. Run smoke checks and one controlled Windows test device before fleet reactivation.
8. Document recovery outcome and any superseding ADR/security response.
