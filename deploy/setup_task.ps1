# Registers the weekly Windows Scheduled Task that refreshes the family dinners page.
# Run once:  powershell -ExecutionPolicy Bypass -File deploy\setup_task.ps1
# Runs deploy.ps1 every Wednesday ~8am; StartWhenAvailable catches up a missed run
# (e.g. PC was off) the next time the PC is on.
$repo   = Split-Path -Parent $PSScriptRoot
$deploy = Join-Path $repo 'deploy.ps1'

$action  = New-ScheduledTaskAction -Execute 'powershell.exe' `
             -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$deploy`""
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Wednesday -At 8:00am
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
             -RunOnlyIfNetworkAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

Register-ScheduledTask -TaskName 'FamilyDinnersRefresh' -Action $action -Trigger $trigger `
    -Settings $settings -Description 'Weekly Coles price refresh + push for the family dinners page' -Force | Out-Null
Write-Output 'Registered scheduled task: FamilyDinnersRefresh (Wednesdays ~8am AWST, catches up if missed).'
