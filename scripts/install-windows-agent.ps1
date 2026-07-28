[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string]$ApiBaseUrl,
    [Parameter(Mandatory = $true)] [string]$EnrollmentToken,
    [string]$InstallDirectory = "$env:ProgramFiles\YorGuard\Agent",
    [string]$ServiceName = "YorGuardAgent"
)

$ErrorActionPreference = "Stop"
$project = Join-Path $PSScriptRoot "..\apps\windows-agent\GSWGuard.Agent\GSWGuard.Agent.csproj"
$publish = Join-Path $env:TEMP "yorguard-agent-publish"

if (-not ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Run this installer from an elevated PowerShell window."
}

dotnet publish $project -c Release -r win-x64 --self-contained false -o $publish
New-Item -ItemType Directory -Force -Path $InstallDirectory | Out-Null
Copy-Item "$publish\*" $InstallDirectory -Recurse -Force

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

$service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($service) { Stop-Service $ServiceName -Force -ErrorAction SilentlyContinue; sc.exe delete $ServiceName | Out-Null }
sc.exe create $ServiceName binPath= "`"$InstallDirectory\GSWGuard.Agent.exe`"" start= auto DisplayName= "YorGuard Agent" | Out-Null
sc.exe description $ServiceName "YorGuard endpoint inventory and health receiver" | Out-Null
Start-Service $ServiceName
Write-Host "YorGuard Agent installed and started. The enrollment token is used once; the device credential is protected with Windows DPAPI."
