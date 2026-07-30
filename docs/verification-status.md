# YorGuard verification-status map

Last reviewed: 2026-07-28

This is the starting artifact for future work. It distinguishes what the phase
reports claimed, what has been directly verified in the current tree or live
test environment, and what remains a gate. Do not treat a phase report alone
as release evidence.

| Unit | Current status | Direct evidence | Remaining gate |
| --- | --- | --- | --- |
| 0A | Verified documentation | Architecture plan and trust-boundary documents exist | Keep ADRs current when a deferred decision is made |
| 0B | Verified foundation | Security policy and baseline threat model exist | Production signing/update trust still unresolved |
| 1A | Evidence incomplete | CI/tooling exists, but there is no dedicated Phase 1A completion report | Verify CI jobs after release changes |
| 1B | Partially verified | Dashboard production build passes; API tests pass; Windows agent builds with .NET 10.0.302 and its test passes | Real Windows Service install/runtime test |
| 1C | Partially verified | Contract/documentation checks pass | Re-run C# contract validation after Windows build is repaired |
| 2 | Partially verified | Supabase-backed sign-in/API membership works in the Pi test environment | Full migration/pgTAP execution and backup/restore evidence |
| 3 | Partially verified | Real Mac enrollment and heartbeat accepted by the Pi API | Real Windows enrollment; credential rotation; HTTPS rollout |
| 4 | Partially verified | Real Mac inventory submission accepted and displayed | Windows collector must compile and run on a real device |
| 5 | Code/test foundation | Phase report and local Python tests | Real scheduler, notification delivery, and retention behavior |
| 6 | Partially verified | Persistent safe inventory jobs were claimed and completed by the Mac receiver | Real Windows job polling; no privileged action handler is approved |
| 7 | Code/test foundation | Compliance code and tests exist | Live policy evaluation and owner-approved remediation rules |
| 8 | Gated/not release-ready | Threat model and package-validation foundation exist | Signed Windows update chain, real package delivery, and Windows validation |
| 9 | Gated/not externally proven | Local provider/tests and threat model exist | Production provider, Windows reparse/ACL tests, malware boundary |
| 10 | Code/test foundation | Audit code/tests and migration exist | Production append-only database path, exports, retention worker |
| 11 | Partially verified | Raspberry Pi API/dashboard are deployed and health checks pass | Windows 11 validation, backups/restore, signed release, production HTTPS/monitoring |

## Current release gate: Windows update chain

Status: **still blocked, but for one remaining reason: no Windows end-to-end
install/update test has been performed, and the agent changes of 2026-07-29 have
not been compiled.** The signing chain itself is now verified.

Directly verified on 2026-07-29 (see [the 2026-07-29 audit](audit-2026-07-29.md)):

- The published `v0.1.1` manifest signature validates against the 2048-bit RSA
  public key pinned in `scripts/YorGuardIntegrity.ps1`, and the package SHA-256
  matches the signed manifest. Checked independently in Python and again through
  `Assert-YorGuardPackageIntegrity` itself.
- `scripts/test-yorguard-integrity.ps1` passes 15/15 fail-closed checks and no
  longer needs the production private key, so it now runs in CI on every change
  (`update-trust` job).
- Corrections 1-5 below are closed. Correction 6 is closed except for the
  Windows end-to-end test.
- Pinning to an immutable release (correction 4) had silently killed the update
  path: the updater polled a `version.txt` pinned to the installed release, so
  the comparison was always equal. Replaced with a **signed channel pointer**,
  so discovery is authenticated while executable bytes still come only from
  immutable per-version URLs.

Remaining before any Windows endpoint rollout:

1. Run `dotnet build` and `dotnet test` on Windows CI for the 2026-07-29
   `Worker.cs` / `DeviceCredentialStore.cs` changes. They could not be compiled
   where they were written (arm64 Linux, TFM `net10.0-windows`).
2. Publish one release containing `channel.txt`/`channel.sig` and perform a real
   install, then a real update, on a Windows 11 machine.

### Original correction list (for history)

Directly verified on 2026-07-28:

- The existing Windows updater downloads and runs packages as `SYSTEM` without
  cryptographic verification.
- The supplied security patch's RSA verifier works in PowerShell 7.6.4 for a
  valid package and rejects modified packages, manifests, signatures, keys,
  versions, and an unconfigured public-key placeholder.
- The patch's Python suite passes: 39 tests.
- The patch's PowerShell scripts parse successfully.
- The Windows agent was repaired and verified locally with .NET 10.0.302:
  `dotnet build` completed with 0 errors and the test suite passed (1 test).

Security-patch corrections required before application:

1. Establish a trusted first-install verifier; never download the verifier
   itself without verifying it.
2. Preserve `appsettings.json` during agent updates and remove the consumed
   enrollment token after successful enrollment.
3. Use a verifier compatible with the PowerShell runtime used by the scheduled
   task, or invoke and package a tested runtime explicitly.
4. Bind installer, package, manifest, and signature to one immutable signed
   release version rather than `releases/latest`.
5. Decide and test the HTTPS/Tailscale transport rollout before enabling the
   new plaintext-transport rejection.
6. Generate the signing keypair, configure the GitHub signing secret, pin the
   public key, publish a new signed release, and perform one Windows end-to-end
   install/update test.

## Operating procedure

For every future unit:

1. Read this map and the one relevant phase report.
2. Inspect the current implementation and existing tests before changing code.
3. Make only the changes needed to close that unit's stated gate.
4. Run the relevant automated tests and one real integration test when the unit
   touches a live boundary.
5. Update this map with commands/results and commit that evidence with the fix.
