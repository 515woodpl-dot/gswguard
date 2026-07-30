# YorGuard audit remediation — July 29, 2026

Follow-up to [`docs/audit-2026-07-29.md`](../audit-2026-07-29.md). Every item
below was applied and verified on the Raspberry Pi the same day.

## Live deployment

- Bound both containers to loopback (`127.0.0.1:8000:8000`, `127.0.0.1:3000:3000`).
  They were on `0.0.0.0`, which put enrollment, heartbeat and inventory on the
  local network in plaintext, bypassing the Tailscale HTTPS boundary.
- Split `.env.local` into shared config plus API-only `.env.secrets.local`. The
  dashboard container no longer receives `DATABASE_URL`, `SUPABASE_JWT_SECRET`
  or `SUPABASE_SERVICE_ROLE_KEY`; it reads none of them.
- Rebuilt and redeployed both images. Health checks pass through Tailscale Serve.

## Database

- Migration `0012_client_roles_read_only.sql`: dropped six client-write RLS
  policies and revoked `insert, update, delete, truncate, references, trigger`
  from `anon`/`authenticated` on all 23 public tables, plus the matching default
  privileges. Supabase's defaults had granted full DML on every table, so RLS
  was the only control rather than defence in depth.
- Migration `0013_audit_actor_no_cascade.sql`: dropped the `ON DELETE SET NULL`
  foreign keys on `audit_log.actor_user_id` and `actor_device_id`. They collided
  with the append-only trigger, making it impossible to delete any device or
  auth user that had emitted an audit event.

## API

- Compliance now distinguishes missing evidence from failure (`RuleOutcome`:
  `passed` / `failed` / `unknown`). Scores are computed over measured weight
  only, and `score` is `null` when nothing could be measured.
- `RemediationGuard` now fires only on a measured `failed`. It previously tested
  `not evidence.passed`, which is also true for missing evidence, so a policy
  with automatic remediation enabled could have submitted a privileged
  remediation job against a device that simply had not reported the field.
- A missing `Authorization` header on the device routes now returns 401 rather
  than 422, via a shared `device_credential_header` dependency. A human `Bearer`
  token still cannot satisfy a device credential.
- The rate limiter is exposed on `app.state` so it can be inspected and reset.

## Tests

- API suite: **40 to 168 tests**.
- `apps/api/tests/test_authorization.py` (118 tests) covers organization scoping,
  role gates, and the device-credential boundary for every route. The key
  assertions are that a forged `organization_id` claim does not change the scope
  used, and that the database role beats the token's `role` claim.
- `apps/api/tests/conftest.py` snapshots `app.state`, fixing pre-existing
  order-dependence. Verified order-independent across three orderings.
- Mutation-tested: removing the membership boundary, dropping a role gate,
  accepting `Bearer` as a device credential, scoring unknown evidence as failed,
  and loosening the remediation guard were each caught (8, 3, 5, 8 and 1 failures
  respectively).

## Windows update chain

- `update-windows-agent.ps1` rewritten around a **signed channel pointer**. It
  fetches `releases/latest/download/channel.txt` plus `channel.sig`, verifies the
  signature against the pinned key, and only then builds immutable per-version
  URLs. This restores updates, which could never fire before, without weakening
  the trust model: executable bytes still come only from a URL bound to one
  signed release, and the package hash is still checked against its signed
  manifest.
- Added rollback: the updater snapshots the install directory and restores it if
  the new build fails to start.
- `install-windows-agent.ps1` now ACLs the install directory to
  SYSTEM + Administrators **before** writing `appsettings.json`, which carries
  the single-use enrollment token. The default Program Files ACL grants
  `Users: Read`, so any local user could previously read the token and race the
  service to enrol a rogue device.
- Added `sc.exe failure` recovery actions and `$LASTEXITCODE` checks on all
  native commands.
- `YorGuardIntegrity.ps1` refactored to one shared `Test-YorGuardSignature`
  helper using `RSA::Create()` with explicit PKCS#1 padding, replacing the
  obsolete `SHA256Managed` path. Behaviour is unchanged: the published v0.1.1
  release still verifies against the pinned production key.
- The release workflow publishes and signs `channel.txt`/`channel.sig`.

## CI

- `npm ci` replaces `npm install`, so the dashboard lockfile is enforced.
- Dashboard `lint` added; it existed but ran in no job.
- New `update-trust` job runs the integrity suite and parses every PowerShell
  script. `scripts/test-yorguard-integrity.ps1` now generates its own throwaway
  keypair, so it needs no signing secret.

## Verification

| Check | Result |
| --- | --- |
| API tests | 168 passed |
| Python syntax (app, tests, receiver) | clean |
| Contract generation/drift | passed |
| Dashboard TypeScript + production build | passed |
| Documentation validation | passed |
| PowerShell integrity suite | 15/15 passed |
| PowerShell parse (4 scripts) | clean |
| Workflow YAML parse | 3 files, 11 jobs |
| Live: loopback binding | `127.0.0.1` only; LAN refused |
| Live: Tailscale API + dashboard health | 200 / 200 |
| Live: unauthenticated `/api/v1/devices` | 401 |
| Live: `/device/jobs/claim` without credential | 401 |
| Live: RLS write policies / grants remaining | 0 / 0 |
| Live: real v0.1.1 release vs pinned key | accepted; tampering rejected |

## Not done

- **Windows security collectors.** `WindowsInventoryCollector.cs` still reports
  `not_collected` for all six security fields, so policies remain unscoreable.
  The engine and dashboard now say so honestly instead of reporting 0%. This
  needs a Windows dev loop.
- **Windows CI validation of the agent changes.** `Worker.cs` and
  `DeviceCredentialStore.cs` could not be compiled here: arm64 Linux host, no
  .NET SDK, TFM `net10.0-windows`. Per ADR 0004 Windows CI is authoritative.
- **H5** blocking DB I/O and no connection pooling; **M1** single rate-limit
  bucket behind the loopback proxy; **M2** offline threshold equal to the
  heartbeat interval; **M3** inventory history deleted on every submission;
  **M11** the deployed Pi tree is not a git repository, so none of this is
  committed or diffable from here.
