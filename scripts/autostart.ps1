# Runs Stock Watcher hidden in the background, starting at every login.
#   autostart.ps1 -Enable    install the scheduled task and (re)start it now
#   autostart.ps1 -Disable   remove the task and stop the watcher
#   autostart.ps1 -Stop      stop the watcher (it comes back within 15 min / next login)
#   autostart.ps1 -Status    show whether it's installed and running
param([switch]$Enable, [switch]$Disable, [switch]$Stop, [switch]$Status)

$ErrorActionPreference = "Stop"
$TaskName = "Stock Watcher"
$Root = Split-Path -Parent $PSScriptRoot
$Pythonw = Join-Path $Root ".venv\Scripts\pythonw.exe"
$App = Join-Path $Root "app.py"

function Get-WatcherProcess {
    Get-CimInstance Win32_Process -Filter "Name='pythonw.exe' OR Name='python.exe'" |
        Where-Object { $_.CommandLine -like "*$App*" -or ($_.CommandLine -like "*app.py*" -and $_.ExecutablePath -like "$Root*") }
}

function Stop-Watcher {
    $procs = @(Get-WatcherProcess)
    foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force }
    Write-Host "Stopped $($procs.Count) Stock Watcher process(es)."
}

if ($Enable) {
    if (-not (Test-Path $Pythonw)) { throw "Can't find $Pythonw - is the .venv set up?" }
    Stop-Watcher  # so running this again doubles as "restart" (e.g. after editing .env or config.yaml)
    $action = New-ScheduledTaskAction -Execute $Pythonw -Argument "`"$App`"" -WorkingDirectory $Root
    # Start at login, then re-check every 15 minutes. If it's already running the
    # extra start is ignored, so this doubles as a watchdog: if the app crashes or the
    # external drive was unplugged at login, it comes back on its own.
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
    $trigger.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15)).Repetition
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 5)
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
        -Principal $principal -Description "Stock Watcher market scanner + dashboard ($Root)" -Force | Out-Null
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "Autostart enabled. Stock Watcher is running in the background."
    Write-Host "Dashboard: http://127.0.0.1:5000   Log: $Root\data\watcher.log"
}
elseif ($Disable) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Autostart removed."
    } else { Write-Host "Autostart was not installed." }
    Stop-Watcher
}
elseif ($Stop) { Stop-Watcher }
else {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Write-Host ("Autostart: " + $(if ($task) { "installed ($($task.State))" } else { "not installed" }))
    $procs = @(Get-WatcherProcess)
    Write-Host ("Running:   " + $(if ($procs) { "yes (PID $($procs.ProcessId -join ', '))" } else { "no" }))
}
