# Registers a Task Scheduler task that runs notification-bridge in the background
# at logon (no console window). Re-run to update settings; -Uninstall to remove.
#
# Prerequisite:
#   uv tool install "notification-bridge[windows] @ https://github.com/payneio/attention-firewall/archive/refs/heads/main.zip"
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File windows-logon-task.ps1 -BucketName notifications-worklaptop
param(
    [string]$CentralContextUrl = "https://central-context.civil.payne.io",
    [string]$BucketName = "notifications-$($env:COMPUTERNAME.ToLower())",
    [int]$Port = 9001,
    [string]$TaskName = "notification-bridge",
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"

if ($Uninstall) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed task '$TaskName'."
    return
}

# pythonw (not the notification-bridge.exe shim) so no console window appears
$toolDir = (& uv tool dir).Trim()
$pythonw = Join-Path $toolDir "notification-bridge\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) {
    throw "Not found: $pythonw. Install notification-bridge with 'uv tool install' first."
}

# Settings are read from .env in the task's working directory
$configDir = Join-Path $env:LOCALAPPDATA "notification-bridge"
New-Item -ItemType Directory -Force $configDir | Out-Null
$logFile = Join-Path $configDir "bridge.log"
$envFile = Join-Path $configDir ".env"
# ASCII, not Set-Content -Encoding utf8: Windows PowerShell adds a BOM that breaks the first key
@"
CENTRAL_CONTEXT_URL=$CentralContextUrl
BUCKET_NAME=$BucketName
HOST=127.0.0.1
PORT=$Port
LOG_FILE=$logFile
"@ | Set-Content -Encoding ascii $envFile

$user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute $pythonw `
    -Argument "-m notification_bridge.main" -WorkingDirectory $configDir
# Interactive logon: the notification listener needs the user's desktop session
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew -StartWhenAvailable

Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

Write-Host "Registered and started task '$TaskName' (runs at logon as $user)."
Write-Host "  config: $envFile"
Write-Host "  log:    $logFile"
Write-Host "  health: http://127.0.0.1:$Port/health"
