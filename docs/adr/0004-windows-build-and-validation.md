# ADR 0004: Windows build and validation strategy

- Status: Proposed
- Date: 2026-07-24

## Context

The agent is a .NET Windows Worker Service and uses Windows-only capabilities such as DPAPI, Windows Event Log, service control, Authenticode, named pipes, Defender, BitLocker, and Winget. The current development host is macOS and has no `dotnet` executable.

## Decision

Run dashboard/API checks on Linux-compatible CI jobs and pin agent build/test jobs to `windows-latest`. Use mocks and unit tests for privileged or destructive behavior. Windows CI validates compilation, serialization, DPAPI adapters, signature verification, service packaging checks, and non-destructive capability detection. It must not run destructive BitLocker, Defender, Firewall, Windows Update, or service-control tests on shared runners. A dedicated Windows 11 test device or VM is required before release for enrollment, service lifecycle, notification, package execution, file operations, and security-policy integration tests.

The agent’s abstractions must permit non-Windows fakes for local tests. Every phase report labels code as written/not built, built/not executed, fake-tested, or Windows-integrated. No macOS/Linux result is presented as Windows validation.

## Consequences

Local agent builds are unavailable until a Windows host/runner is used, but the strategy is honest and reproducible. CI configuration and a Windows-specific test matrix are Phase 1A/1B work; production-device validation is Phase 11.
