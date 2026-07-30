# YorGuard Windows MSI

The MSI installs the self-contained Windows agent, its enrollment helper, the
signed update verifier, and the automatic Windows service `YorGuardAgent`.

The MSI intentionally does not contain an enrollment token. Each computer must
use its own one-time token after installation:

```powershell
& 'C:\Program Files\YorGuard\Agent\YorGuardEnroll.exe' `
  --api-base-url 'https://gsw.tail8a6b99.ts.net:8443'
```

The helper prompts privately for the token, writes the configuration with
LocalSystem/Administrators-only permissions, and starts the service. The agent
then consumes the token during enrollment and removes it from the settings.

For Intune, deploy the MSI as a Win32 app and use a separate per-device
enrollment bootstrap to supply the unique token. Do not bake a token into a
shared MSI or commit one to source control.

Release publication requires Authenticode signing. Configure the GitHub
Actions secrets `MSI_SIGNING_PFX_B64` and `MSI_SIGNING_PFX_PASSWORD` before
tagging a release; the release workflow refuses to publish an unsigned MSI.
