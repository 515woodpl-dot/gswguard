# YorGuard Windows agent

This is a small Windows Service. It enrolls with a one-time token, stores the device credential with Windows DPAPI, then automatically sends a heartbeat and inventory snapshot every five minutes. It collects approved metadata only: OS/build, hardware, disks, network adapters, local account names, and installed software names/versions. It does not collect browser history, document contents, or user files.

From an elevated PowerShell prompt on the Windows computer, copy only `scripts/install-windows-agent.ps1` and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\install-windows-agent.ps1 `
  -ApiBaseUrl "http://100.127.37.0:8000" `
  -EnrollmentToken "paste-the-one-time-token-here"
```

The installer downloads the current self-contained Windows package, registers the service, and creates a six-hour scheduled updater. Future tagged releases are downloaded and installed automatically; `appsettings.json` and the protected device credential are preserved. The token is consumed during enrollment and the protected device credential is stored under `C:\ProgramData\YorGuard`.

Useful service commands:

```powershell
Get-Service YorGuardAgent
Restart-Service YorGuardAgent
```

Validation runs on `windows-latest` because the current development host has no .NET SDK or Windows APIs:

```text
dotnet build GSWGuard.Agent.slnx
dotnet test GSWGuard.Agent.slnx
```

Configure the receiver with environment variables before starting the agent:

```powershell
$env:Agent__ApiBaseUrl = "http://100.127.37.0:8000"
$env:Agent__EnrollmentToken = "yorg_enroll_..."
$env:Agent__DeviceName = $env:COMPUTERNAME
```

On first start, the agent consumes the one-time token, stores the device credential using Windows DPAPI, and sends a heartbeat every five minutes. The enrollment token is never written to logs.

For macOS development, use the native helper from the repository root:

```bash
python3 scripts/yorguard-receiver.py --watch 30 --jobs
```

It prompts privately for a token once, stores the device credential in macOS Keychain, and sends a heartbeat every five minutes.

To keep the Mac receiver running automatically after login, install its LaunchAgent once:

```bash
bash scripts/install-macos-receiver.sh
```

After installation, the receiver runs in the background, sends heartbeats, claims safe inventory-refresh jobs, collects approved device metadata locally, and submits snapshots. The enrollment token and device credential remain outside the LaunchAgent plist.
The worker intentionally performs no device management or command execution and does not claim production readiness.
