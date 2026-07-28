# YorGuard — Work Completed Today

Date: 2026-07-28

## Mac endpoint inventory

- Added automatic macOS inventory collection through the background receiver.
- The receiver now reports inventory during its heartbeat cycle without requiring a Terminal command.
- Added collection for macOS model, serial number, OS version, CPU, RAM, disk usage, installed applications, and local account metadata.
- Installed and verified the macOS LaunchAgent:
  - `com.yorguard.receiver`
  - Runs automatically after login.
  - Sends heartbeats every five minutes.
- Added API support for inventory submission and latest inventory retrieval.
- Added cross-platform OS-version support to the inventory schema.
- Fixed the initial inventory failure caused by the API rejecting the Mac `os_version` field.
- Verified a real Mac inventory submission was accepted with HTTP 200.

## Inventory retention

- Changed inventory storage to keep one current snapshot per device.
- A new inventory report replaces the previous snapshot for that device.
- Removed obsolete accumulated `refresh_inventory` test jobs from the Raspberry Pi database.
- Removed the manual inventory-refresh control from the dashboard.
- Inventory reporting is now described as automatic in the dashboard.

## Dashboard fixes

- Added latest inventory summaries to each device row:
  - Last capture time.
  - CPU.
  - RAM.
  - Installed application count.
- Fixed stale “Failed to fetch” messages remaining visible after a successful retry.
- Dashboard now shows only the latest job status per device/action instead of repeated test history.
- Dashboard and API were redeployed to the Raspberry Pi and health checks passed.

## Windows endpoint agent

- Extended the Windows Worker Service from a skeleton into an automatic inventory agent.
- Added Windows collection for:
  - Windows edition, version, and build.
  - CPU and logical processors.
  - Installed RAM.
  - Local disks and free space.
  - Active network adapters and IP addresses.
  - Local account names.
  - Installed software names, publishers, and versions.
- Added Windows API inventory submission.
- Credentials are stored using Windows DPAPI under `C:\ProgramData\YorGuard`.
- The service sends heartbeat and inventory data every five minutes.

## Windows bootstrap and self-update

- Added `scripts/install-windows-agent.ps1`.
- The installer:
  - Downloads the current self-contained Windows agent package.
  - Installs the YorGuard Windows Service.
  - Stores the API URL and enrollment configuration.
  - Starts the service automatically.
  - Creates a scheduled updater task.
- Added `scripts/update-windows-agent.ps1`.
- The updater checks every six hours for a newer release, updates the agent, preserves configuration, and restarts the service.
- Added `.github/workflows/windows-agent-release.yml`.
- Tagged releases build and publish the Windows package automatically.

## Dashboard Windows bootstrap download

- Added a dashboard button to download a one-file Windows bootstrap script.
- The downloaded script contains the API URL and that computer’s one-time enrollment token.
- The user copies only that file to Windows and runs it once as Administrator.
- The token is not committed to GitHub or logged by YorGuard.

## Git and release

- Main branch was pushed to GitHub.
- Initial release tag created and pushed:

```text
v0.1.0
```

- Latest commit: `4ff6c5e` — Add one-file Windows bootstrap download.

## Verification completed

- Python API tests: 35 passed.
- Dashboard production build: passed.
- Documentation validation: passed.
- Python receiver syntax validation: passed.
- Raspberry Pi API health: healthy.
- Raspberry Pi dashboard health: healthy.
- Mac heartbeat: accepted.
- Mac inventory submission: accepted with HTTP 200.

## Remaining verification

- Confirm the GitHub Actions Windows release workflow completes successfully for `v0.1.0`.
- Download the dashboard-generated bootstrap on a Windows computer.
- Run the bootstrap once as Administrator.
- Confirm the Windows device appears in the YorGuard dashboard with inventory data.
