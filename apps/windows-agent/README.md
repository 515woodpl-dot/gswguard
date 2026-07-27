# YorGuard Windows agent

Minimal .NET 10 Worker Service skeleton. It supports console/development hosting and Windows Service hosting, loads typed configuration, and has no privileged management handlers yet.

Validation runs on `windows-latest` because the current development host has no .NET SDK or Windows APIs:

```text
dotnet build GSWGuard.Agent.slnx
dotnet test GSWGuard.Agent.slnx
```

The worker intentionally performs no device management, does not store credentials, does not execute commands, and does not claim production readiness.
