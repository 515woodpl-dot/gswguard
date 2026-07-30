<#
.SYNOPSIS
Install and enroll YorGuard from the Windows MSI package.

.DESCRIPTION
Run this script from an elevated Windows PowerShell window on the target
computer. It installs the MSI, prompts for the computer's one-time token
without putting the token in the process command line, enrolls the agent, and
verifies the Windows service and updater task.

.EXAMPLE
Set-ExecutionPolicy -Scope Process Bypass -Force
.\install-windows-agent-msi.ps1 -MsiPath .\YorGuardAgent.msi
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$MsiPath,
    [string]$ApiBaseUrl = "https://gsw.tail8a6b99.ts.net:8443",
    [string]$InstallDirectory = "$env:ProgramFiles\YorGuard\Agent",
    [string]$MsiLogPath = "$env:TEMP\YorGuardAgent-msi-install.log",
    [string]$EnrollmentToken
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Fail([string]$message) {
    throw "YorGuard installation failed: $message"
}

function Assert-Administrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Fail "open PowerShell with Run as administrator and run this script again."
    }
}

function Assert-Https([string]$url) {
    $parsed = $null
    if (-not [Uri]::TryCreate($url, [UriKind]::Absolute, [ref]$parsed) -or $parsed.Scheme -ne "https") {
        Fail "ApiBaseUrl must be an absolute https:// URL."
    }
}

function Read-TokenSecurely {
    $secure = Read-Host "Paste this computer's one-time enrollment token" -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Invoke-Enroller([string]$helperPath, [string]$apiUrl, [string]$token) {
    # The token is sent through standard input, never as a command-line
    # argument. This keeps it out of typical process listings and event logs.
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $helperPath
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.Arguments = '--api-base-url "' + $apiUrl.Replace('"', '\"') + '" --enrollment-token-stdin'

    $process = [Diagnostics.Process]::Start($startInfo)
    try {
        $process.StandardInput.WriteLine($token)
        $process.StandardInput.Close()
        $stdout = $process.StandardOutput.ReadToEnd()
        $stderr = $process.StandardError.ReadToEnd()
        $process.WaitForExit()
        $exitCode = $process.ExitCode
    } finally {
        $process.Dispose()
    }

    if ($stdout) { Write-Host $stdout.TrimEnd() }
    if ($exitCode -ne 0) {
        if ($stderr) { Write-Error $stderr.TrimEnd() }
        Fail "enrollment helper exited with code $exitCode."
    }
}

Assert-Administrator
Assert-Https $ApiBaseUrl

$resolvedMsi = (Resolve-Path -LiteralPath $MsiPath -ErrorAction SilentlyContinue).Path
if (-not $resolvedMsi -or -not (Test-Path -LiteralPath $resolvedMsi -PathType Leaf)) {
    Fail "MSI was not found at '$MsiPath'."
}

$msi = Get-Item -LiteralPath $resolvedMsi
if ($msi.Length -lt 1MB) {
    Fail "MSI is unexpectedly small ($($msi.Length) bytes). Download and extract the YorGuardAgent-msi artifact again."
}

Write-Host "Installing $($msi.Name)..."
$installer = Start-Process -FilePath "$env:SystemRoot\System32\msiexec.exe" `
    -ArgumentList @('/i', "`"$resolvedMsi`"", '/passive', '/norestart', '/L*v', "`"$MsiLogPath`"") `
    -Wait -PassThru
if ($installer.ExitCode -notin @(0, 3010)) {
    Fail "Windows Installer returned $($installer.ExitCode). See $MsiLogPath"
}

$helper = Join-Path $InstallDirectory "YorGuardEnroll.exe"
if (-not (Test-Path -LiteralPath $helper -PathType Leaf)) {
    Fail "MSI completed, but the enrollment helper was not found at '$helper'. See $MsiLogPath"
}

if ([string]::IsNullOrWhiteSpace($EnrollmentToken)) {
    $EnrollmentToken = Read-TokenSecurely
}
if ([string]::IsNullOrWhiteSpace($EnrollmentToken) -or $EnrollmentToken.Length -lt 20) {
    Fail "the enrollment token is empty or too short."
}

Write-Host "Enrolling this computer..."
Invoke-Enroller $helper $ApiBaseUrl $EnrollmentToken

$service = Get-Service -Name "YorGuardAgent" -ErrorAction SilentlyContinue
if (-not $service -or $service.Status -ne "Running") {
    Fail "YorGuardAgent is not running after enrollment. See $MsiLogPath"
}

$task = Get-ScheduledTask -TaskName "YorGuardAgentUpdater" -ErrorAction SilentlyContinue
if (-not $task) {
    Fail "YorGuardAgentUpdater was not registered."
}

Write-Host ""
Write-Host "YorGuard installed and enrolled successfully."
Write-Host "Service: $($service.Status)"
Write-Host "Updater: registered"
Write-Host "MSI log: $MsiLogPath"
