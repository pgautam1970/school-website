# Registers a Windows Task Scheduler job that runs the daily report at 19:00 and retries
# every 15 minutes for 5 hours if delivery has not been accepted yet.
#
# IMPORTANT: Task Scheduler uses THIS computer's clock and time zone. Set Windows to
# "(UTC+05:45) Kathmandu" or use the in-app scheduler (KVI_SCHEDULER_ENABLED=true), which
# always uses Asia/Kathmandu explicitly. Use one of the two, not both, to avoid confusion
# (duplicates are prevented either way).
#
# Run in PowerShell as the account that owns the install:
#   powershell -ExecutionPolicy Bypass -File scripts\windows\register_daily_task.ps1
param(
  [string]$InstallDir = (Resolve-Path "$PSScriptRoot\..\..").Path,
  [string]$TaskName = "KVI Daily School Intelligence Report",
  [string]$At = "19:00"
)
$runBat = Join-Path $InstallDir "scripts\windows\run_daily.bat"
if (-not (Test-Path $runBat)) { throw "run_daily.bat not found at $runBat" }
$action  = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$runBat`"" -WorkingDirectory $InstallDir
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At $At -RepetitionInterval (New-TimeSpan -Minutes 15) -RepetitionDuration (New-TimeSpan -Hours 5)).Repetition
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "KVI daily report at 19:00 Asia/Kathmandu (idempotent)" -Force | Out-Null
Write-Host "Registered '$TaskName' at $At daily (retry every 15 min for 5 h until accepted)."
