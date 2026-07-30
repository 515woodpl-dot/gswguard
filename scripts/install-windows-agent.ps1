<#
.SYNOPSIS
Installs and starts the YorGuard Windows endpoint agent.

.EXAMPLE
Set-ExecutionPolicy -Scope Process Bypass
.\install-windows-agent.ps1 `
  -ApiBaseUrl "https://gsw.tail8a6b99.ts.net:8443" `
  -EnrollmentToken "PASTE_THIS_COMPUTER_S_ONE_TIME_TOKEN_HERE"

Run PowerShell as Administrator. Create the one-time token in the YorGuard
dashboard immediately before installation. Do not save the real token in Git.
#>

[CmdletBinding()]
param(
    [string]$ApiBaseUrl = "https://gsw.tail8a6b99.ts.net:8443",
    [Parameter(Mandatory = $true)] [string]$EnrollmentToken,
    [string]$InstallDirectory = "$env:ProgramFiles\YorGuard\Agent",
    [string]$ServiceName = "YorGuardAgent",
    [string]$PackageUrl = "https://github.com/515woodpl-dot/gswguard/releases/download/v0.1.1/yorguard-windows-agent.zip",
    [string]$VersionUrl = "https://github.com/515woodpl-dot/gswguard/releases/download/v0.1.1/version.txt",
    [string]$ManifestUrl = "https://github.com/515woodpl-dot/gswguard/releases/download/v0.1.1/manifest.txt",
    [string]$SignatureUrl = "https://github.com/515woodpl-dot/gswguard/releases/download/v0.1.1/manifest.sig",
    # Releases root the scheduled updater polls for a SIGNED channel pointer.
    # The install itself uses the immutable pinned URLs above; the updater needs
    # a stable location to learn that a newer signed release exists at all.
    [string]$ReleaseBaseUrl = "https://github.com/515woodpl-dot/gswguard/releases",
    [string]$PackagePath,
    [string]$ManifestPath,
    [string]$SignaturePath,
    # Allow plaintext HTTP only when explicitly acknowledged (e.g. a lab on a
    # trusted tailnet). Defaults to requiring TLS for every remote URL.
    [switch]$AllowInsecureHttp
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this installer from an elevated PowerShell window."
}

# --- Transport safety -------------------------------------------------------
# The API URL carries the device credential and, indirectly, the update trust
# path. Require HTTPS unless the operator explicitly opts into plaintext.
function Assert-SecureUrl([string]$url, [string]$label) {
    if ($url -notmatch '^https://' ) {
        $isLoopback = $url -match '^https?://(localhost|127\.0\.0\.1)([:/]|$)'
        if ($AllowInsecureHttp -or $isLoopback) {
            Write-Warning "$label uses plaintext HTTP: $url"
        } else {
            throw "$label must use https:// (got '$url'). Re-run with -AllowInsecureHttp to override on a trusted network."
        }
    }
}
Assert-SecureUrl $ApiBaseUrl "ApiBaseUrl"
foreach ($u in @($PackageUrl, $VersionUrl, $ManifestUrl, $SignatureUrl, $ReleaseBaseUrl)) {
    Assert-SecureUrl $u "Download URL"
}

# Native commands ignore $ErrorActionPreference, so their exit codes have to be
# checked explicitly or a failed service registration stays silent.
function Invoke-Native([string]$description, [scriptblock]$command) {
    $output = & $command 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "$description failed with exit code ${LASTEXITCODE}: $output"
    }
}

$download = $PackagePath
$manifest = $ManifestPath
$signature = $SignaturePath
$extract  = Join-Path $env:TEMP "yorguard-agent-install"
$temporaryInputs = @()

if ([string]::IsNullOrWhiteSpace($download) -or [string]::IsNullOrWhiteSpace($manifest) -or [string]::IsNullOrWhiteSpace($signature)) {
    if ($PackagePath -or $ManifestPath -or $SignaturePath) {
        throw "PackagePath, ManifestPath, and SignaturePath must be supplied together."
    }
    $download = Join-Path $env:TEMP "yorguard-windows-agent.zip"
    $manifest = Join-Path $env:TEMP "yorguard-manifest.txt"
    $signature = Join-Path $env:TEMP "yorguard-manifest.sig"
    $temporaryInputs = @($download, $manifest, $signature)
    Invoke-WebRequest -Uri $PackageUrl   -OutFile $download  -UseBasicParsing
    Invoke-WebRequest -Uri $ManifestUrl  -OutFile $manifest  -UseBasicParsing
    Invoke-WebRequest -Uri $SignatureUrl -OutFile $signature -UseBasicParsing
} elseif (-not (Test-Path $download) -or -not (Test-Path $manifest) -or -not (Test-Path $signature)) {
    throw "A supplied verified package input is missing."
}

# The installer must be launched from the signed package, or from a directory
# containing the verifier shipped with that package. Never download verifier
# code from the network and execute it.
$verifierLocal = Join-Path $PSScriptRoot "YorGuardIntegrity.ps1"
if (-not (Test-Path $verifierLocal)) {
    throw "Trusted YorGuardIntegrity.ps1 is missing beside the installer; refusing to continue."
}
. $verifierLocal

# Fail closed unless the package is signed by the pinned key and hashes match.
$verifiedVersion = Assert-YorGuardPackageIntegrity `
    -PackagePath $download -ManifestPath $manifest -SignaturePath $signature

Remove-Item $extract -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive -Path $download -DestinationPath $extract -Force
New-Item -ItemType Directory -Force -Path $InstallDirectory | Out-Null

# Lock the install directory down BEFORE writing appsettings.json into it. That
# file carries the single-use enrollment token until the service consumes it,
# and the default Program Files ACL grants Users:Read - so without this any
# standard user on the machine could read the token and race the service to
# enrol a rogue device.
$acl = Get-Acl $InstallDirectory
$acl.SetAccessRuleProtection($true, $false)
foreach ($rule in @($acl.Access)) { [void]$acl.RemoveAccessRule($rule) }
foreach ($sid in @(
    [Security.Principal.WellKnownSidType]::LocalSystemSid,
    [Security.Principal.WellKnownSidType]::BuiltinAdministratorsSid
)) {
    $acl.AddAccessRule((New-Object Security.AccessControl.FileSystemAccessRule(
        (New-Object Security.Principal.SecurityIdentifier($sid, $null)),
        [Security.AccessControl.FileSystemRights]::FullControl,
        [Security.AccessControl.InheritanceFlags]"ContainerInherit, ObjectInherit",
        [Security.AccessControl.PropagationFlags]::None,
        [Security.AccessControl.AccessControlType]::Allow)))
}
Set-Acl -Path $InstallDirectory -AclObject $acl

Copy-Item "$extract\*" $InstallDirectory -Recurse -Force
Set-Content (Join-Path $InstallDirectory "version.txt") -Value $verifiedVersion -Encoding ASCII

$settings = @{
    Agent = @{
        Environment = "production"
        Version = $verifiedVersion
        ApiBaseUrl = $ApiBaseUrl.TrimEnd('/')
        EnrollmentToken = $EnrollmentToken
        DeviceName = $env:COMPUTERNAME
        Manufacturer = ""
        Model = ""
        SerialNumber = ""
    }
    Logging = @{ LogLevel = @{ Default = "Information"; "Microsoft.Hosting.Lifetime" = "Information" } }
} | ConvertTo-Json -Depth 5
$settings | Set-Content (Join-Path $InstallDirectory "appsettings.json") -Encoding UTF8
# Remove the pointer file left by older installs. The updater now discovers
# versions through the signed channel pointer under $ReleaseBaseUrl, so a stale
# pinned version URL on disk would only mislead whoever reads it next.
Remove-Item (Join-Path $InstallDirectory "update-version-url.txt") -Force -ErrorAction SilentlyContinue

$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($service) {
    Stop-Service $ServiceName -Force -ErrorAction SilentlyContinue
    Invoke-Native "sc.exe delete $ServiceName" { sc.exe delete $ServiceName }
}
Invoke-Native "sc.exe create $ServiceName" {
    sc.exe create $ServiceName binPath= "`"$InstallDirectory\GSWGuard.Agent.exe`"" start= auto DisplayName= "YorGuard Agent"
}
Invoke-Native "sc.exe description $ServiceName" {
    sc.exe description $ServiceName "YorGuard endpoint inventory and health receiver"
}
# Recovery actions: the baseline threat model requires the service to come back
# after a crash rather than silently leaving the endpoint unmanaged.
Invoke-Native "sc.exe failure $ServiceName" {
    sc.exe failure $ServiceName reset= 86400 actions= restart/60000/restart/60000/restart/300000
}
Start-Service $ServiceName

# The updater discovers new versions through the SIGNED channel pointer under
# $ReleaseBaseUrl. It is deliberately NOT pinned to this install's release URLs:
# doing that made the version check always compare equal, so updates never ran.
$updaterArguments = @(
    "-NoProfile", "-ExecutionPolicy", "Bypass",
    "-File", "`"$InstallDirectory\update-windows-agent.ps1`"",
    "-InstallDirectory", "`"$InstallDirectory`"",
    "-ReleaseBaseUrl", "`"$($ReleaseBaseUrl.TrimEnd('/'))`"",
    "-ServiceName", "`"$ServiceName`""
) -join " "
Invoke-Native "schtasks.exe /Create YorGuardAgentUpdater" {
    & "$env:SystemRoot\System32\schtasks.exe" /Create /TN "YorGuardAgentUpdater" /SC HOURLY /MO 6 /RU SYSTEM /F `
        /TR "powershell.exe $updaterArguments"
}

# The enrollment token is cleared by the service after successful enrollment;
# clear only the transient download inputs here.
Remove-Item $temporaryInputs -Force -ErrorAction SilentlyContinue
Write-Host "YorGuard Agent $verifiedVersion installed and started. Package signature verified; device credential is protected with Windows DPAPI."
