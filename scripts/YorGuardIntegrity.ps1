# YorGuard package-integrity verification.
#
# Shared by install-windows-agent.ps1 and update-windows-agent.ps1 so the trust
# decision lives in exactly one reviewed place. Verification uses only the
# .NET RSA primitives built into PowerShell, so endpoints need no extra tooling.
#
# Trust model:
#   * Releases publish a manifest (version + sha256 of the package) and a
#     detached RSA-SHA256 signature over that manifest.
#   * Releases also publish a signed channel pointer naming the current version,
#     so update discovery is authenticated too and does not depend on trusting a
#     mutable URL.
#   * The signing PUBLIC key is pinned below, embedded in the agent scripts that
#     ship with each machine. Trust is anchored to the key, NOT to the URL the
#     package is fetched from. Tampering with the release, the CDN, DNS, or the
#     transport cannot forge a package without the private key.
#   * The package is only trusted if BOTH the signature verifies against the
#     pinned key AND the package's SHA-256 matches the signed manifest.
#
# Known limitation: a signed pointer has no expiry, so an attacker who controls
# the transport can replay an older signed channel file and stall updates. That
# is a freshness/denial problem, not a forgery one - downgrade protection in
# update-windows-agent.ps1 still refuses to install anything older than what is
# present. The channel file carries issued_at so a stale pointer is at least
# visible in the log.
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

function Get-YorGuardPinnedPublicKeyXml {
    if ([string]::IsNullOrWhiteSpace($script:YorGuardSigningPublicKeyXmlBase64) -or
        $script:YorGuardSigningPublicKeyXmlBase64 -like "REPLACE_*") {
        throw "Release-signing public key is not configured; refusing to trust anything."
    }
    return [System.Text.Encoding]::UTF8.GetString(
        [Convert]::FromBase64String($script:YorGuardSigningPublicKeyXmlBase64))
}

function Test-YorGuardSignature {
    <#
    .SYNOPSIS
    Return $true when the detached base64 RSA-SHA256 signature over $Data
    verifies against the pinned public key. Never throws on a bad signature;
    callers decide what a failure means.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)] [byte[]]$Data,
        [Parameter(Mandatory = $true)] [string]$SignatureBase64
    )

    $signature = [Convert]::FromBase64String($SignatureBase64.Trim())
    # RSA::Create() with explicit PKCS#1 padding. Works on Windows PowerShell
    # 5.1 and PowerShell 7, and avoids the obsolete SHA256Managed type.
    $rsa = [System.Security.Cryptography.RSA]::Create()
    try {
        $rsa.FromXmlString((Get-YorGuardPinnedPublicKeyXml))
        return $rsa.VerifyData(
            $Data,
            $signature,
            [System.Security.Cryptography.HashAlgorithmName]::SHA256,
            [System.Security.Cryptography.RSASignaturePadding]::Pkcs1)
    } finally {
        $rsa.Dispose()
    }
}

function ConvertFrom-YorGuardSignedFields {
    <#
    .SYNOPSIS
    Parse `key=value` lines from an already-signature-verified byte array.
    #>
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)] [byte[]]$Data)

    $fields = @{}
    $text = [System.Text.Encoding]::ASCII.GetString($Data)
    foreach ($line in ($text -split "`n")) {
        if ($line -match '^\s*([^=]+)=(.*)$') {
            $fields[$matches[1].Trim()] = $matches[2].Trim()
        }
    }
    return $fields
}

function Get-YorGuardSignedChannelVersion {
    <#
    .SYNOPSIS
    Return the release version named by a signed channel pointer.

    .DESCRIPTION
    Update discovery has to come from a mutable location - there is no other way
    to learn that a newer release exists - so the pointer itself is signed. The
    version it names is then used to build immutable per-version download URLs,
    which keeps the property that executable bytes are only ever fetched from a
    URL bound to one signed release.
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)] [string]$ChannelPath,
        [Parameter(Mandatory = $true)] [string]$SignaturePath
    )

    $ErrorActionPreference = "Stop"

    foreach ($p in @($ChannelPath, $SignaturePath)) {
        if (-not (Test-Path $p)) { throw "Channel input missing: $p" }
    }

    $channelBytes = [System.IO.File]::ReadAllBytes($ChannelPath)
    if (-not (Test-YorGuardSignature -Data $channelBytes -SignatureBase64 (Get-Content -Raw $SignaturePath))) {
        throw "Channel pointer signature is INVALID. Refusing to act on it."
    }

    $fields = ConvertFrom-YorGuardSignedFields -Data $channelBytes
    if (-not $fields.ContainsKey("version") -or [string]::IsNullOrWhiteSpace($fields["version"])) {
        throw "Signed channel pointer has no version field."
    }

    if ($fields.ContainsKey("issued_at") -and -not [string]::IsNullOrWhiteSpace($fields["issued_at"])) {
        [datetime]$issued = [datetime]::MinValue
        if ([datetime]::TryParse($fields["issued_at"], [ref]$issued)) {
            $age = (Get-Date).ToUniversalTime() - $issued.ToUniversalTime()
            if ($age.TotalDays -gt 45) {
                Write-Warning ("YorGuard channel pointer is {0:N0} days old; update discovery may be stalled." -f $age.TotalDays)
            }
        }
    }

    return $fields["version"]
}

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

    # 1. Verify the detached signature over the manifest bytes with the pinned key.
    $manifestBytes = [System.IO.File]::ReadAllBytes($ManifestPath)
    if (-not (Test-YorGuardSignature -Data $manifestBytes -SignatureBase64 (Get-Content -Raw $SignaturePath))) {
        throw "Package manifest signature is INVALID. Aborting; the package is not trusted."
    }

    # 2. Parse the now-trusted manifest.
    $fields = ConvertFrom-YorGuardSignedFields -Data $manifestBytes
    $signedHash = if ($fields.ContainsKey("sha256")) { $fields["sha256"] } else { "" }
    $signedVersion = if ($fields.ContainsKey("version")) { $fields["version"] } else { "" }
    $signedFile = if ($fields.ContainsKey("file")) { $fields["file"] } else { "" }
    if ([string]::IsNullOrWhiteSpace($signedHash)) { throw "Signed manifest has no sha256 field." }
    if ([string]::IsNullOrWhiteSpace($signedVersion)) { throw "Signed manifest has no version field." }
    if ($signedFile -ne "yorguard-windows-agent.zip") { throw "Signed manifest names an unexpected package file." }

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
