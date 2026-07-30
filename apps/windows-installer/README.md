# YorGuard Windows MSI

The MSI installs the self-contained Windows agent, its enrollment helper, the
signed update verifier, and the automatic Windows service `YorGuardAgent`.

For a simple test installation, copy the MSI and
`scripts/install-windows-agent-msi.ps1` to the same folder, then run the
bootstrap script from an elevated PowerShell window:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
Set-Location "$env:USERPROFILE\Downloads\YorGuardAgent-msi"
.\install-windows-agent-msi.ps1 -MsiPath .\YorGuardAgent.msi
```

The script installs the MSI, writes an installation log to
`%TEMP%\YorGuardAgent-msi-install.log`, prompts for the computer's one-time
token without echoing it or putting it in the process command line, and checks
that the agent service and updater task were created.

The MSI intentionally does not contain an enrollment token. For direct
enrollment after the MSI is already installed, run:

```powershell
& 'C:\Program Files\YorGuard\Agent\YorGuardEnroll.exe' `
  --api-base-url 'https://gsw.tail8a6b99.ts.net:8443'
```

The helper writes the configuration with LocalSystem/Administrators-only
permissions and starts the service. The agent then consumes the token during
enrollment and removes it from the settings.

For Intune, deploy the MSI as a Win32 app and use a separate per-device
enrollment bootstrap to supply the unique token. Do not bake a token into a
shared MSI or commit one to source control.

Release publication requires Authenticode signing. Configure the GitHub
Actions secrets `MSI_SIGNING_PFX_B64` and `MSI_SIGNING_PFX_PASSWORD` before
tagging a release; the release workflow refuses to publish an unsigned MSI.
