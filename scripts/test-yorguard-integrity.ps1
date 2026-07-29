[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$PrivateKeyPath,
    [string]$Version = "v0.1.1"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

. (Join-Path $PSScriptRoot "YorGuardIntegrity.ps1")

$root = Join-Path ([IO.Path]::GetTempPath()) ("yorguard-integrity-test-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $root | Out-Null
try {
    $payload = Join-Path $root "payload.txt"
    $package = Join-Path $root "yorguard-windows-agent.zip"
    $manifest = Join-Path $root "manifest.txt"
    $signature = Join-Path $root "manifest.sig"
    Set-Content -Path $payload -Value "signed test payload" -Encoding ASCII
    Compress-Archive -Path $payload -DestinationPath $package

    $hash = (Get-FileHash $package -Algorithm SHA256).Hash.ToLower()
    $manifestText = "version=$Version" + [Environment]::NewLine + "sha256=$hash" + [Environment]::NewLine + "file=yorguard-windows-agent.zip" + [Environment]::NewLine
    Set-Content -Path $manifest -Value $manifestText -NoNewline -Encoding ASCII

    $privateDer = [IO.File]::ReadAllBytes($PrivateKeyPath)
    $rsa = [Security.Cryptography.RSA]::Create()
    try {
        $read = 0
        $rsa.ImportPkcs8PrivateKey($privateDer, [ref]$read)
        $bytes = [IO.File]::ReadAllBytes($manifest)
        $sig = $rsa.SignData(
            $bytes,
            [Security.Cryptography.HashAlgorithmName]::SHA256,
            [Security.Cryptography.RSASignaturePadding]::Pkcs1)
    } finally {
        $rsa.Dispose()
    }
    Set-Content -Path $signature -Value ([Convert]::ToBase64String($sig)) -NoNewline -Encoding ASCII

    $verified = Assert-YorGuardPackageIntegrity -PackagePath $package -ManifestPath $manifest -SignaturePath $signature -ExpectedVersion $Version
    if ($verified -ne $Version) { throw "Valid package returned unexpected version: $verified" }
    Write-Host "valid signature accepted"

    $tamperedPackage = Join-Path $root "tampered-package.zip"
    Copy-Item $package $tamperedPackage
    Add-Content -Path $tamperedPackage -Value "tampered"
    $failed = $false
    try { Assert-YorGuardPackageIntegrity -PackagePath $tamperedPackage -ManifestPath $manifest -SignaturePath $signature | Out-Null } catch { $failed = $true }
    if (-not $failed) { throw "Tampered package was accepted." }
    Write-Host "tampered package rejected"

    $tamperedManifest = Join-Path $root "tampered-manifest.txt"
    Copy-Item $manifest $tamperedManifest
    Add-Content -Path $tamperedManifest -Value "unexpected=true"
    $failed = $false
    try { Assert-YorGuardPackageIntegrity -PackagePath $package -ManifestPath $tamperedManifest -SignaturePath $signature | Out-Null } catch { $failed = $true }
    if (-not $failed) { throw "Tampered manifest was accepted." }
    Write-Host "tampered manifest rejected"

    $failed = $false
    try { Assert-YorGuardPackageIntegrity -PackagePath $package -ManifestPath $manifest -SignaturePath $signature -ExpectedVersion "v9.9.9" | Out-Null } catch { $failed = $true }
    if (-not $failed) { throw "Wrong expected version was accepted." }
    Write-Host "wrong version rejected"

    $badSignature = Join-Path $root "bad-signature.sig"
    Set-Content -Path $badSignature -Value ([Convert]::ToBase64String((1..256 | ForEach-Object { [byte]0 }))) -NoNewline -Encoding ASCII
    $failed = $false
    try { Assert-YorGuardPackageIntegrity -PackagePath $package -ManifestPath $manifest -SignaturePath $badSignature | Out-Null } catch { $failed = $true }
    if (-not $failed) { throw "Invalid signature was accepted." }
    Write-Host "invalid signature rejected"
}
finally {
    Remove-Item $root -Recurse -Force -ErrorAction SilentlyContinue
}
