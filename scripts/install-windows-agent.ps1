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
foreach ($u in @($PackageUrl, $VersionUrl, $ManifestUrl, $SignatureUrl)) {
    Assert-SecureUrl $u "Download URL"
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
$VersionUrl | Set-Content (Join-Path $InstallDirectory "update-version-url.txt") -Encoding UTF8

$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($service) { Stop-Service $ServiceName -Force -ErrorAction SilentlyContinue; sc.exe delete $ServiceName | Out-Null }
sc.exe create $ServiceName binPath= "`"$InstallDirectory\GSWGuard.Agent.exe`"" start= auto DisplayName= "YorGuard Agent" | Out-Null
sc.exe description $ServiceName "YorGuard endpoint inventory and health receiver" | Out-Null
Start-Service $ServiceName
& "$env:SystemRoot\System32\schtasks.exe" /Create /TN "YorGuardAgentUpdater" /SC HOURLY /MO 6 /RU SYSTEM /F /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$InstallDirectory\update-windows-agent.ps1`" -PackageUrl `"$PackageUrl`" -VersionUrl `"$VersionUrl`" -ManifestUrl `"$ManifestUrl`" -SignatureUrl `"$SignatureUrl`" -InstallDirectory `"$InstallDirectory`" -ServiceName `"$ServiceName`"" | Out-Null

# The enrollment token is cleared by the service after successful enrollment;
# clear only the transient download inputs here.
Remove-Item $temporaryInputs -Force -ErrorAction SilentlyContinue
Write-Host "YorGuard Agent $verifiedVersion installed and started. Package signature verified; device credential is protected with Windows DPAPI."
