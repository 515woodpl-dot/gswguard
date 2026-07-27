# YorGuard Windows agent

Minimal .NET 10 Worker Service skeleton. It supports console/development hosting and Windows Service hosting, loads typed configuration, and has no privileged management handlers yet.

Validation runs on `windows-latest` because the current development host has no .NET SDK or Windows APIs:

```text
dotnet build GSWGuard.Agent.slnx
dotnet test GSWGuard.Agent.slnx

Configure the receiver with environment variables before starting the agent:

```powershell
$env:Agent__ApiBaseUrl = "http://100.127.37.0:8000"
$env:Agent__EnrollmentToken = "yorg_enroll_..."
$env:Agent__DeviceName = $env:COMPUTERNAME
```

On first start, the agent consumes the one-time token, stores the device credential using Windows DPAPI, and sends a heartbeat every five minutes. The enrollment token is never written to logs.
```

The worker intentionally performs no device management, does not store credentials, does not execute commands, and does not claim production readiness.
