[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$PackageUrl,
    [Parameter(Mandatory = $true)] [string]$VersionUrl,
    [Parameter(Mandatory = $true)] [string]$InstallDirectory,
    [string]$ServiceName = "YorGuardAgent"
)

$ErrorActionPreference = "Stop"
$tempRoot = Join-Path $env:TEMP "yorguard-agent-update"
$zip = Join-Path $tempRoot "agent.zip"
$extract = Join-Path $tempRoot "extract"
$currentVersionPath = Join-Path $InstallDirectory "version.txt"
$remoteVersion = (Invoke-WebRequest -Uri $VersionUrl -UseBasicParsing).Content.Trim()
$currentVersion = if (Test-Path $currentVersionPath) { (Get-Content $currentVersionPath -Raw).Trim() } else { "" }
if ([string]::IsNullOrWhiteSpace($remoteVersion) -or $remoteVersion -eq $currentVersion) { exit 0 }

New-Item -ItemType Directory -Force -Path $tempRoot | Out-Null
Invoke-WebRequest -Uri $PackageUrl -OutFile $zip -UseBasicParsing
Remove-Item $extract -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive -Path $zip -DestinationPath $extract -Force

Stop-Service $ServiceName -Force -ErrorAction SilentlyContinue
Copy-Item "$extract\*" $InstallDirectory -Recurse -Force
Set-Content -Path $currentVersionPath -Value $remoteVersion -Encoding ASCII
Start-Service $ServiceName
