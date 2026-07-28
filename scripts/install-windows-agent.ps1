[<comment-based help>
.SYNOPSIS
Installs and starts the YorGuard Windows endpoint agent.

.EXAMPLE
Set-ExecutionPolicy -Scope Process Bypass
.\install-windows-agent.ps1 `
  -ApiBaseUrl "http://100.127.37.0:8000" `
  -EnrollmentToken "PASTE_THIS_COMPUTER_S_ONE_TIME_TOKEN_HERE"

Run PowerShell as Administrator. Create the one-time token in the YorGuard
dashboard immediately before installation. Do not save the real token in Git.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$ApiBaseUrl,
    [Parameter(Mandatory = $true)] [string]$EnrollmentToken,
    [string]$InstallDirectory = "$env:ProgramFiles\YorGuard\Agent",
    [string]$ServiceName = "YorGuardAgent",
    [string]$PackageUrl = "https://github.com/515woodpl-dot/gswguard/releases/latest/download/yorguard-windows-agent.zip",
    [string]$VersionUrl = "https://github.com/515woodpl-dot/gswguard/releases/latest/download/version.txt"
)

$ErrorActionPreference = "Stop"
$download = Join-Path $env:TEMP "yorguard-windows-agent.zip"
$extract = Join-Path $env:TEMP "yorguard-agent-install"

if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this installer from an elevated PowerShell window."
}

Invoke-WebRequest -Uri $PackageUrl -OutFile $download
Remove-Item $extract -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive -Path $download -DestinationPath $extract -Force
New-Item -ItemType Directory -Force -Path $InstallDirectory | Out-Null
Copy-Item "$extract\*" $InstallDirectory -Recurse -Force

$settings = @{
    Agent = @{
        Environment = "production"
        Version = "0.1.0"
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
& "$env:SystemRoot\System32\schtasks.exe" /Create /TN "YorGuardAgentUpdater" /SC HOURLY /MO 6 /RU SYSTEM /F /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$InstallDirectory\update-windows-agent.ps1`" -PackageUrl `"$PackageUrl`" -VersionUrl `"$VersionUrl`" -InstallDirectory `"$InstallDirectory`" -ServiceName `"$ServiceName`"" | Out-Null
Write-Host "YorGuard Agent installed and started. The enrollment token is used once; the device credential is protected with Windows DPAPI."
