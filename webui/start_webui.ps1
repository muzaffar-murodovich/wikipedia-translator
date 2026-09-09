# webui/start_webui.ps1
# Starts the web UI once, hidden, without waiting for a logon event - useful
# for testing setup_autostart.ps1's result manually, or for starting it back
# up mid-session after ending it in Task Manager. This is the exact command
# the scheduled task itself runs.

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonwExe = Join-Path $repoRoot ".venv\Scripts\pythonw.exe"
$entryScript = Join-Path $repoRoot "webui\run_webui.pyw"

Start-Process -FilePath $pythonwExe -ArgumentList "`"$entryScript`"" -WindowStyle Hidden
Write-Host "Ishga tushirildi: http://127.0.0.1:5057" -ForegroundColor Green
