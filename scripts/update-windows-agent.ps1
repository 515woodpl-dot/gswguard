<#
.SYNOPSIS
Update the YorGuard Windows agent to the current signed release.

.DESCRIPTION
Discovery is authenticated. The updater fetches a signed channel pointer from a
stable URL, verifies it against the pinned release-signing public key, and only
then builds immutable per-version download URLs for the version it names.

This replaces the previous design, which polled a version.txt pinned to the
already-installed release. That comparison was always equal, so the updater
exited 0 every time and no endpoint could ever receive an update.

Executable bytes are still only ever fetched from a URL bound to one signed
release, and the package hash is still checked against its signed manifest.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$InstallDirectory,
    # Repository releases root, e.g.
    #   https://github.com/<owner>/<repo>/releases
    [Parameter(Mandatory = $true)] [string]$ReleaseBaseUrl,
    [string]$ServiceName = "YorGuardAgent",
    # Overrides, mainly for testing against a staging release set.
    [string]$ChannelUrl,
    [string]$ChannelSignatureUrl,
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

$releaseRoot = $ReleaseBaseUrl.TrimEnd('/')
if (-not $ChannelUrl)          { $ChannelUrl          = "$releaseRoot/latest/download/channel.txt" }
if (-not $ChannelSignatureUrl) { $ChannelSignatureUrl = "$releaseRoot/latest/download/channel.sig" }

Assert-SecureUrl $releaseRoot "ReleaseBaseUrl"
Assert-SecureUrl $ChannelUrl "Channel URL"
Assert-SecureUrl $ChannelSignatureUrl "Channel signature URL"

# Load the shared, pinned-key verification routines that ship alongside the agent.
$verifier = Join-Path $InstallDirectory "YorGuardIntegrity.ps1"
if (-not (Test-Path $verifier)) {
    throw "Trusted YorGuardIntegrity.ps1 is missing from $InstallDirectory; refusing to continue."
}
. $verifier

$tempRoot = Join-Path $env:TEMP ("yorguard-agent-update-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null

try {
    $channel = Join-Path $tempRoot "channel.txt"
    $channelSig = Join-Path $tempRoot "channel.sig"
    $currentVersionPath = Join-Path $InstallDirectory "version.txt"
    $currentVersion = if (Test-Path $currentVersionPath) { (Get-Content $currentVersionPath -Raw).Trim() } else { "" }

    # 1. Authenticated discovery. A forged or unsigned pointer stops us here.
    Invoke-WebRequest -Uri $ChannelUrl -OutFile $channel -UseBasicParsing
    Invoke-WebRequest -Uri $ChannelSignatureUrl -OutFile $channelSig -UseBasicParsing
    $targetVersion = Get-YorGuardSignedChannelVersion -ChannelPath $channel -SignaturePath $channelSig

    if ($targetVersion -eq $currentVersion) {
        Write-Host "YorGuard agent is already on the current signed release ($currentVersion)."
        exit 0
    }

    # 2. Immutable, per-version download URLs for the version the signed pointer
    #    named. Never 'latest' for executable bytes.
    $versionRoot = "$releaseRoot/download/$targetVersion"
    $packageUrl = "$versionRoot/yorguard-windows-agent.zip"
    $manifestUrl = "$versionRoot/manifest.txt"
    $signatureUrl = "$versionRoot/manifest.sig"
    foreach ($u in @($packageUrl, $manifestUrl, $signatureUrl)) { Assert-SecureUrl $u "Download URL" }

    $zip = Join-Path $tempRoot "agent.zip"
    $manifest = Join-Path $tempRoot "manifest.txt"
    $signature = Join-Path $tempRoot "manifest.sig"
    $extract = Join-Path $tempRoot "extract"

    Invoke-WebRequest -Uri $packageUrl   -OutFile $zip       -UseBasicParsing
    Invoke-WebRequest -Uri $manifestUrl  -OutFile $manifest  -UseBasicParsing
    Invoke-WebRequest -Uri $signatureUrl -OutFile $signature -UseBasicParsing

    # 3. Fail closed unless the package is signed by the pinned key, its hash
    #    matches the signed manifest, and the manifest names exactly the version
    #    the signed channel pointer advertised.
    $verifiedVersion = Assert-YorGuardPackageIntegrity `
        -PackagePath $zip -ManifestPath $manifest -SignaturePath $signature `
        -ExpectedVersion $targetVersion

    # 4. Downgrade protection: never move to an older or equal version.
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

    Expand-Archive -Path $zip -DestinationPath $extract -Force
    if (-not (Test-Path (Join-Path $extract "GSWGuard.Agent.exe"))) {
        throw "Signed package does not contain the agent executable."
    }

    # 5. Keep a rollback copy so a package that will not start does not leave the
    #    endpoint with a stopped service and no way back.
    $backup = Join-Path $tempRoot "previous"
    New-Item -ItemType Directory -Force -Path $backup | Out-Null
    Copy-Item (Join-Path $InstallDirectory "*") $backup -Recurse -Force -ErrorAction SilentlyContinue

    Stop-Service $ServiceName -Force -ErrorAction SilentlyContinue
    try {
        # appsettings.json holds the enrollment/API configuration for this
        # machine and must survive the update.
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
        Write-Host "YorGuard agent updated from '$currentVersion' to '$verifiedVersion'."
    } catch {
        Write-Warning "Update to $verifiedVersion failed: $($_.Exception.Message). Rolling back to $currentVersion."
        Get-ChildItem -LiteralPath $backup -Force |
            Where-Object { $_.Name -ne "appsettings.json" } |
            Copy-Item -Destination $InstallDirectory -Recurse -Force -ErrorAction SilentlyContinue
        if ($currentVersion) {
            Set-Content -Path $currentVersionPath -Value $currentVersion -Encoding ASCII
        }
        Start-Service $ServiceName -ErrorAction SilentlyContinue
        throw
    }
} finally {
    Remove-Item $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
