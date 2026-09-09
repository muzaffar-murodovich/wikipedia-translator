# webui/setup_autostart.ps1
# One-time setup: installs webui's own dependencies into the project's
# existing venv and registers a Windows Task Scheduler task that starts the
# web UI, hidden, whenever this user logs in.
#
# Assumes the normal project setup (CLAUDE.md / README.md) is already done:
#   python -m venv .venv ; pip install -r requirements.txt ; .env with OPENAI_API_KEY

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $repoRoot ".venv\Scripts\python.exe"
$pythonwExe = Join-Path $repoRoot ".venv\Scripts\pythonw.exe"
$entryScript = Join-Path $repoRoot "webui\run_webui.pyw"
$taskName = "WikipediaTranslatorWebUI"

if (-not (Test-Path $pythonwExe)) {
    Write-Host "Xato: $pythonwExe topilmadi." -ForegroundColor Red
    Write-Host "Avval loyihaning asosiy sozlashini bajaring:" -ForegroundColor Yellow
    Write-Host "  python -m venv .venv"
    Write-Host "  .venv\Scripts\pip install -r requirements.txt"
    Write-Host "  .env faylida OPENAI_API_KEY'ni sozlang (CLAUDE.md/README.md'ga qarang)"
    exit 1
}

Write-Host "webui uchun kerakli paketlar o'rnatilmoqda..."
& $pythonExe -m pip install -r (Join-Path $repoRoot "webui\requirements.txt")

Write-Host "Avtostart vazifasi ro'yxatga olinmoqda..."
$action = "`"$pythonwExe`" `"$entryScript`""
schtasks /create /tn $taskName /tr $action /sc onlogon /rl limited /f | Out-Null

Write-Host "Vazifa hozir sinov uchun ishga tushirilmoqda..."
schtasks /run /tn $taskName | Out-Null

Start-Sleep -Seconds 2
Write-Host ""
Write-Host "Tayyor! Brauzerda oching va xatcho'p qiling:" -ForegroundColor Green
Write-Host "  http://127.0.0.1:5057" -ForegroundColor Cyan
Write-Host ""
Write-Host "Endi kompyuterga har kirishda avtomatik ishga tushadi (fon jarayoni)."
Write-Host "O'chirish uchun: webui\uninstall_autostart.ps1"
