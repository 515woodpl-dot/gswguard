[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$PackageUrl,
    [Parameter(Mandatory = $true)] [string]$VersionUrl,
    [Parameter(Mandatory = $true)] [string]$InstallDirectory,
    [string]$ServiceName = "YorGuardAgent",
    # Base URL the manifest and signature are fetched from. Defaults to deriving
    # them from the package URL's directory (the GitHub release folder).
    [string]$ManifestUrl,
    [string]$SignatureUrl,
    [switch]$AllowInsecureHttp
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Assert-SecureUrl([string]$url, [string]$label) {
    if ($url -notmatch '^https://') {
        $isLoopback = $url -match '^https?://(localhost|127\.0\.0\.1)([:/]|$)'
        if ($AllowInsecureHttp -or $isLoopback) {
            Write-Warning "$label uses plaintext HTTP: $url"
        } else {
            throw "$label must use https:// (got '$url')."
        }
    }
}
foreach ($u in @($PackageUrl, $VersionUrl, $ManifestUrl, $SignatureUrl)) {
    if ($u) { Assert-SecureUrl $u "Download URL" }
}

# Load the shared, pinned-key verification routine that ships alongside the agent.
. (Join-Path $InstallDirectory "YorGuardIntegrity.ps1")

if (-not $ManifestUrl)  { $ManifestUrl  = ($PackageUrl -replace '[^/]+$', 'manifest.txt') }
if (-not $SignatureUrl) { $SignatureUrl = ($PackageUrl -replace '[^/]+$', 'manifest.sig') }

$tempRoot = Join-Path $env:TEMP "yorguard-agent-update"
$zip = Join-Path $tempRoot "agent.zip"
$manifest = Join-Path $tempRoot "manifest.txt"
$signature = Join-Path $tempRoot "manifest.sig"
$extract = Join-Path $tempRoot "extract"
$currentVersionPath = Join-Path $InstallDirectory "version.txt"

New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null

# The advertised version is only a hint for "is there maybe something new"; it is
# NOT trusted for the update decision. The authoritative version comes from the
# signed manifest after verification.
$remoteVersion = (Invoke-WebRequest -Uri $VersionUrl -UseBasicParsing).Content.Trim()
$currentVersion = if (Test-Path $currentVersionPath) { (Get-Content $currentVersionPath -Raw).Trim() } else { "" }
if ([string]::IsNullOrWhiteSpace($remoteVersion) -or $remoteVersion -eq $currentVersion) { exit 0 }

Invoke-WebRequest -Uri $PackageUrl   -OutFile $zip       -UseBasicParsing
Invoke-WebRequest -Uri $ManifestUrl  -OutFile $manifest  -UseBasicParsing
Invoke-WebRequest -Uri $SignatureUrl -OutFile $signature -UseBasicParsing

# Fail closed unless the downloaded package is signed by the pinned key and its
# hash matches the signed manifest. Returns the trusted version string.
$verifiedVersion = Assert-YorGuardPackageIntegrity `
    -PackagePath $zip -ManifestPath $manifest -SignaturePath $signature `
    -ExpectedVersion $remoteVersion

# Downgrade protection: never "update" to an older or equal version. Uses a
# best-effort semantic comparison, falling back to string inequality.
function ConvertTo-Comparable([string]$v) {
    $clean = $v.TrimStart('v')
    [version]$parsed = $null
    if ([version]::TryParse($clean, [ref]$parsed)) { return $parsed }
    return $null
}
$new = ConvertTo-Comparable $verifiedVersion
$cur = ConvertTo-Comparable $currentVersion
if ($new -and $cur -and $new -le $cur) {
    throw "Refusing downgrade: verified version $verifiedVersion is not newer than installed $currentVersion."
}

Remove-Item $extract -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive -Path $zip -DestinationPath $extract -Force

Stop-Service $ServiceName -Force -ErrorAction SilentlyContinue
Get-ChildItem -LiteralPath $extract -Force |
    Where-Object { $_.Name -ne "appsettings.json" } |
    Copy-Item -Destination $InstallDirectory -Recurse -Force
Set-Content -Path $currentVersionPath -Value $verifiedVersion -Encoding ASCII
$settingsPath = Join-Path $InstallDirectory "appsettings.json"
if (Test-Path $settingsPath) {
    $settings = Get-Content -Raw -Path $settingsPath | ConvertFrom-Json
    $settings.Agent.Version = $verifiedVersion
    $settings | ConvertTo-Json -Depth 10 | Set-Content -Path $settingsPath -Encoding UTF8
}
Start-Service $ServiceName

Remove-Item $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
