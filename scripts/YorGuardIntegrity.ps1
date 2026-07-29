# YorGuard package-integrity verification.
#
# Shared by install-windows-agent.ps1 and update-windows-agent.ps1 so the trust
# decision lives in exactly one reviewed place. Verification uses only the
# .NET RSA primitives built into Windows PowerShell, so endpoints need no extra
# tooling.
#
# Trust model:
#   * Releases publish a manifest (version + sha256 of the package) and a
#     detached RSA-SHA256 signature over that manifest.
#   * The signing PUBLIC key is pinned below, embedded in the agent scripts that
#     ship with each machine. Trust is anchored to the key, NOT to the URL the
#     package is fetched from. Tampering with the release, the CDN, DNS, or the
#     transport cannot forge a package without the private key.
#   * The package is only trusted if BOTH the signature verifies against the
#     pinned key AND the package's SHA-256 matches the signed manifest.
#
# Rotating the key: publish releases signed by the new key, ship an agent update
# (verified under the OLD key) that carries the NEW pinned key, then retire the
# old key. Never accept an unsigned or hash-only package.

Set-StrictMode -Version Latest

# --- Pinned release-signing public key (RSA XML, base64 UTF-8) --------------
# Replace this placeholder with the base64-encoded RSA XML public key before
# the first signed release. The matching private key lives only in the
# RELEASE_SIGNING_PRIVATE_KEY GitHub secret. RSA XML is used because it is
# supported by both Windows PowerShell 5.1 and PowerShell 7.
$script:YorGuardSigningPublicKeyXmlBase64 = "PFJTQUtleVZhbHVlPjxNb2R1bHVzPnFhcnFReU9HcmJlZUxSbXZrUURkYU5uV1NOWnJJWFZPdkY3QjZxRWZsZ1I2dkRmWWpIU1FtRGpWYUNjQ2tGZndCSGhFWG9BUXc0bXJqSTRIekI2L0FBV0RMTHM5STFjd09ldnBRb2FXSGV5OHpOS3ZaRG5BNU4rd0NIRGc5czRBbk5KZWR3bkk4RmFnSjVaSXI2Z3RjZ3htRmViYU1OTTRJd1pLWmwyanhlRnp1YmNDYnpKNDE1ZU9YK1VHa2tlRmtwTld0M0U5VHpMSzhoWUpzTU1LamdXUXZSQXFhcVBKdDcyT3ZBYWVqVERxQ2Vubml2ekZQU2tVR3U4WU5rdGhua1VlTmxjWTA4RkxiVnAzNTZhTFZDZVE3Z0drTVNud1ZxajV2VGovR2JaZC81Rk9oUUFMa2kwbzZ5OW1pZ0tocUxQV2djd1NUSWNHSEtGd20wS1VwUT09PC9Nb2R1bHVzPjxFeHBvbmVudD5BUUFCPC9FeHBvbmVudD48L1JTQUtleVZhbHVlPg=="

function Assert-YorGuardPackageIntegrity {
    <#
    .SYNOPSIS
    Fail closed unless the package matches a manifest that is validly signed by
    the pinned key. Throws on any mismatch; returns the verified version string.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)] [string]$PackagePath,
        [Parameter(Mandatory = $true)] [string]$ManifestPath,
        [Parameter(Mandatory = $true)] [string]$SignaturePath,
        [string]$ExpectedVersion
    )

    $ErrorActionPreference = "Stop"

    foreach ($p in @($PackagePath, $ManifestPath, $SignaturePath)) {
        if (-not (Test-Path $p)) { throw "Integrity input missing: $p" }
    }

    if ($script:YorGuardSigningPublicKeyXmlBase64 -like "REPLACE_*") {
        throw "Release-signing public key is not configured; refusing to trust the package."
    }

    # 1. Verify the detached signature over the manifest bytes with the pinned key.
    $manifestBytes = [System.IO.File]::ReadAllBytes($ManifestPath)
    $signature = [Convert]::FromBase64String((Get-Content -Raw $SignaturePath).Trim())
    $publicKeyXml = [System.Text.Encoding]::UTF8.GetString(
        [Convert]::FromBase64String($script:YorGuardSigningPublicKeyXmlBase64))

    $rsa = New-Object System.Security.Cryptography.RSACryptoServiceProvider
    $sha256 = New-Object System.Security.Cryptography.SHA256Managed
    try {
        $rsa.FromXmlString($publicKeyXml)
        $ok = $rsa.VerifyData($manifestBytes, $sha256, $signature)
    } finally {
        $sha256.Dispose()
        $rsa.Dispose()
    }
    if (-not $ok) { throw "Package manifest signature is INVALID. Aborting; the package is not trusted." }

    # 2. Parse the now-trusted manifest.
    $manifestText = [System.Text.Encoding]::ASCII.GetString($manifestBytes)
    $fields = @{}
    foreach ($line in ($manifestText -split "`n")) {
        if ($line -match '^\s*([^=]+)=(.*)$') { $fields[$matches[1].Trim()] = $matches[2].Trim() }
    }
    $signedHash = $fields["sha256"]
    $signedVersion = $fields["version"]
    if ([string]::IsNullOrWhiteSpace($signedHash)) { throw "Signed manifest has no sha256 field." }
    if ([string]::IsNullOrWhiteSpace($signedVersion)) { throw "Signed manifest has no version field." }
    if ($fields["file"] -ne "yorguard-windows-agent.zip") { throw "Signed manifest names an unexpected package file." }

    # 3. Optional version pin: block downgrade / wrong-artifact substitution.
    if ($ExpectedVersion -and $signedVersion -ne $ExpectedVersion) {
        throw "Signed manifest version '$signedVersion' does not match expected '$ExpectedVersion'."
    }

    # 4. The signed hash must match the package on disk.
    $actualHash = (Get-FileHash $PackagePath -Algorithm SHA256).Hash.ToLower()
    if ($actualHash -ne $signedHash.ToLower()) {
        throw "Package SHA-256 mismatch. Expected $signedHash but got $actualHash. Aborting."
    }

    return $signedVersion
}
