<#
.SYNOPSIS
Verify YorGuardIntegrity.ps1 fails closed on every tampering case.

.DESCRIPTION
By default this generates a throwaway RSA keypair and tests against a copy of
YorGuardIntegrity.ps1 with the pinned key replaced by the generated public key.
That means the suite needs no secrets and can run in CI on every change to the
trust code. Previously it required the production private key, so it could only
ever be run by hand.

Pass -PrivateKeyPath to instead test the real pinned key against a package you
signed with the matching production key.
#>

[CmdletBinding()]
param(
    [string]$PrivateKeyPath,
    [string]$Version = "v0.1.1"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$script:Failures = 0
$script:Checks = 0

function Assert-Ok([string]$name, [scriptblock]$assertion) {
    $script:Checks++
    try {
        & $assertion
        Write-Host "  PASS  $name"
    } catch {
        $script:Failures++
        Write-Host "  FAIL  $name -> $($_.Exception.Message)"
    }
}

function Assert-Throws([string]$name, [scriptblock]$assertion) {
    # Deliberately not delegating to Assert-Ok: a nested scriptblock that closes
    # over its own parameter name gets rebound to the callee's parameter when
    # invoked there, which recurses forever.
    $script:Checks++
    $threw = $false
    try { & $assertion | Out-Null } catch { $threw = $true }
    if ($threw) {
        Write-Host "  PASS  $name"
    } else {
        $script:Failures++
        Write-Host "  FAIL  $name -> expected a failure but the input was ACCEPTED"
    }
}

$root = Join-Path ([IO.Path]::GetTempPath()) ("yorguard-integrity-test-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $root | Out-Null

try {
    # --- Trust anchor under test -------------------------------------------
    $verifierSource = Join-Path $PSScriptRoot "YorGuardIntegrity.ps1"
    $verifier = Join-Path $root "YorGuardIntegrity.ps1"

    if ($PrivateKeyPath) {
        Write-Host "Testing the PRODUCTION pinned key with the supplied private key."
        Copy-Item $verifierSource $verifier
        $signingKey = [Security.Cryptography.RSA]::Create()
        $read = 0
        $signingKey.ImportPkcs8PrivateKey([IO.File]::ReadAllBytes($PrivateKeyPath), [ref]$read)
    } else {
        Write-Host "Testing with a generated throwaway keypair (no secrets required)."
        $signingKey = [Security.Cryptography.RSA]::Create(2048)
        $publicXmlBase64 = [Convert]::ToBase64String(
            [Text.Encoding]::UTF8.GetBytes($signingKey.ToXmlString($false)))
        # Swap the pinned anchor for the generated one, leaving all logic intact.
        $source = Get-Content -Raw $verifierSource
        $pattern = '(?m)^\$script:YorGuardSigningPublicKeyXmlBase64 = ".*"\r?$'
        $replacement = '$script:YorGuardSigningPublicKeyXmlBase64 = "' + $publicXmlBase64 + '"'
        $patched = [regex]::Replace($source, $pattern, $replacement)
        if ($patched -eq $source) { throw "Could not substitute the pinned key; the anchor line changed shape." }
        Set-Content -Path $verifier -Value $patched -Encoding UTF8
    }

    . $verifier

    function New-Signature([string]$path) {
        $sig = $signingKey.SignData(
            [IO.File]::ReadAllBytes($path),
            [Security.Cryptography.HashAlgorithmName]::SHA256,
            [Security.Cryptography.RSASignaturePadding]::Pkcs1)
        return [Convert]::ToBase64String($sig)
    }

    # --- Fixtures -----------------------------------------------------------
    $payload = Join-Path $root "payload.txt"
    $package = Join-Path $root "yorguard-windows-agent.zip"
    $manifest = Join-Path $root "manifest.txt"
    $signature = Join-Path $root "manifest.sig"
    Set-Content -Path $payload -Value "signed test payload" -Encoding ASCII
    Compress-Archive -Path $payload -DestinationPath $package

    $hash = (Get-FileHash $package -Algorithm SHA256).Hash.ToLower()
    $manifestText = "version=$Version`nsha256=$hash`nfile=yorguard-windows-agent.zip`n"
    Set-Content -Path $manifest -Value $manifestText -NoNewline -Encoding ASCII
    Set-Content -Path $signature -Value (New-Signature $manifest) -NoNewline -Encoding ASCII

    Write-Host "`nPackage manifest verification"

    Assert-Ok "valid signature accepted and returns the signed version" {
        $verified = Assert-YorGuardPackageIntegrity -PackagePath $package -ManifestPath $manifest `
            -SignaturePath $signature -ExpectedVersion $Version
        if ($verified -ne $Version) { throw "returned '$verified'" }
    }

    Assert-Throws "tampered package rejected" {
        $bad = Join-Path $root "tampered-package.zip"
        Copy-Item $package $bad -Force
        Add-Content -Path $bad -Value "tampered"
        Assert-YorGuardPackageIntegrity -PackagePath $bad -ManifestPath $manifest -SignaturePath $signature
    }

    Assert-Throws "tampered manifest rejected" {
        $bad = Join-Path $root "tampered-manifest.txt"
        Copy-Item $manifest $bad -Force
        Add-Content -Path $bad -Value "unexpected=true"
        Assert-YorGuardPackageIntegrity -PackagePath $package -ManifestPath $bad -SignaturePath $signature
    }

    Assert-Throws "wrong expected version rejected" {
        Assert-YorGuardPackageIntegrity -PackagePath $package -ManifestPath $manifest `
            -SignaturePath $signature -ExpectedVersion "v9.9.9"
    }

    Assert-Throws "invalid signature rejected" {
        $bad = Join-Path $root "bad-signature.sig"
        Set-Content -Path $bad -Value ([Convert]::ToBase64String((1..256 | ForEach-Object { [byte]0 }))) -NoNewline -Encoding ASCII
        Assert-YorGuardPackageIntegrity -PackagePath $package -ManifestPath $manifest -SignaturePath $bad
    }

    Assert-Throws "signature from a DIFFERENT key rejected" {
        $foreign = [Security.Cryptography.RSA]::Create(2048)
        try {
            $sig = $foreign.SignData([IO.File]::ReadAllBytes($manifest),
                [Security.Cryptography.HashAlgorithmName]::SHA256,
                [Security.Cryptography.RSASignaturePadding]::Pkcs1)
        } finally { $foreign.Dispose() }
        $bad = Join-Path $root "foreign.sig"
        Set-Content -Path $bad -Value ([Convert]::ToBase64String($sig)) -NoNewline -Encoding ASCII
        Assert-YorGuardPackageIntegrity -PackagePath $package -ManifestPath $manifest -SignaturePath $bad
    }

    Assert-Throws "manifest naming an unexpected package file rejected" {
        $bad = Join-Path $root "wrong-file-manifest.txt"
        Set-Content -Path $bad -Value "version=$Version`nsha256=$hash`nfile=evil.zip`n" -NoNewline -Encoding ASCII
        $badSig = Join-Path $root "wrong-file-manifest.sig"
        Set-Content -Path $badSig -Value (New-Signature $bad) -NoNewline -Encoding ASCII
        Assert-YorGuardPackageIntegrity -PackagePath $package -ManifestPath $bad -SignaturePath $badSig
    }

    Assert-Throws "manifest with no sha256 field rejected" {
        $bad = Join-Path $root "no-hash-manifest.txt"
        Set-Content -Path $bad -Value "version=$Version`nfile=yorguard-windows-agent.zip`n" -NoNewline -Encoding ASCII
        $badSig = Join-Path $root "no-hash-manifest.sig"
        Set-Content -Path $badSig -Value (New-Signature $bad) -NoNewline -Encoding ASCII
        Assert-YorGuardPackageIntegrity -PackagePath $package -ManifestPath $bad -SignaturePath $badSig
    }

    Assert-Throws "missing input file rejected" {
        Assert-YorGuardPackageIntegrity -PackagePath (Join-Path $root "absent.zip") `
            -ManifestPath $manifest -SignaturePath $signature
    }

    # --- Signed channel pointer (audit finding H2) --------------------------
    Write-Host "`nSigned channel pointer"

    $channel = Join-Path $root "channel.txt"
    $channelSig = Join-Path $root "channel.sig"
    $issuedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    Set-Content -Path $channel -Value "version=v0.2.0`nissued_at=$issuedAt`n" -NoNewline -Encoding ASCII
    Set-Content -Path $channelSig -Value (New-Signature $channel) -NoNewline -Encoding ASCII

    Assert-Ok "valid channel pointer returns the advertised version" {
        $v = Get-YorGuardSignedChannelVersion -ChannelPath $channel -SignaturePath $channelSig
        if ($v -ne "v0.2.0") { throw "returned '$v'" }
    }

    Assert-Throws "tampered channel pointer rejected" {
        $bad = Join-Path $root "tampered-channel.txt"
        Set-Content -Path $bad -Value "version=v9.9.9`nissued_at=$issuedAt`n" -NoNewline -Encoding ASCII
        Get-YorGuardSignedChannelVersion -ChannelPath $bad -SignaturePath $channelSig
    }

    Assert-Throws "unsigned channel pointer rejected" {
        $bad = Join-Path $root "unsigned-channel.sig"
        Set-Content -Path $bad -Value ([Convert]::ToBase64String((1..256 | ForEach-Object { [byte]0 }))) -NoNewline -Encoding ASCII
        Get-YorGuardSignedChannelVersion -ChannelPath $channel -SignaturePath $bad
    }

    Assert-Throws "channel pointer with no version field rejected" {
        $bad = Join-Path $root "no-version-channel.txt"
        Set-Content -Path $bad -Value "issued_at=$issuedAt`n" -NoNewline -Encoding ASCII
        $badSig = Join-Path $root "no-version-channel.sig"
        Set-Content -Path $badSig -Value (New-Signature $bad) -NoNewline -Encoding ASCII
        Get-YorGuardSignedChannelVersion -ChannelPath $bad -SignaturePath $badSig
    }

    Assert-Ok "stale channel pointer warns but still resolves" {
        $stale = Join-Path $root "stale-channel.txt"
        $old = (Get-Date).ToUniversalTime().AddDays(-120).ToString("yyyy-MM-ddTHH:mm:ssZ")
        Set-Content -Path $stale -Value "version=v0.2.0`nissued_at=$old`n" -NoNewline -Encoding ASCII
        $staleSig = Join-Path $root "stale-channel.sig"
        Set-Content -Path $staleSig -Value (New-Signature $stale) -NoNewline -Encoding ASCII
        $warnings = @()
        $v = Get-YorGuardSignedChannelVersion -ChannelPath $stale -SignaturePath $staleSig -WarningVariable warnings
        if ($v -ne "v0.2.0") { throw "returned '$v'" }
        if ($warnings.Count -eq 0) { throw "expected a staleness warning" }
    }

    Assert-Throws "unconfigured pinned key refuses to trust anything" {
        $unpinned = Join-Path $root "Unpinned.ps1"
        $src = Get-Content -Raw $verifier
        $src = [regex]::Replace($src, '(?m)^\$script:YorGuardSigningPublicKeyXmlBase64 = ".*"\r?$',
            '$script:YorGuardSigningPublicKeyXmlBase64 = "REPLACE_ME"')
        Set-Content -Path $unpinned -Value $src -Encoding UTF8
        & {
            . $unpinned
            Assert-YorGuardPackageIntegrity -PackagePath $package -ManifestPath $manifest -SignaturePath $signature
        }
    }

    Write-Host ""
    if ($script:Failures -gt 0) {
        throw "$script:Failures of $script:Checks integrity checks FAILED."
    }
    Write-Host "All $script:Checks integrity checks passed."
}
finally {
    if ($signingKey) { $signingKey.Dispose() }
    Remove-Item $root -Recurse -Force -ErrorAction SilentlyContinue
}
