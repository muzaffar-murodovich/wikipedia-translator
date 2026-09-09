# webui/uninstall_autostart.ps1
# Removes the autostart task. The web server itself is not stopped by this
# script (there is no shutdown endpoint, by design - see the plan) - if it
# is currently running, end "pythonw.exe" via Task Manager, or just log off
# and back on once the task is gone.

$ErrorActionPreference = "Stop"
$taskName = "WikipediaTranslatorWebUI"

schtasks /delete /tn $taskName /f
Write-Host "Avtostart vazifasi o'chirildi: $taskName" -ForegroundColor Green
