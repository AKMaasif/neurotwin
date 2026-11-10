# Sets up and starts IFHAS-NeuroTwin on Windows. Safe to run again: steps already done are skipped.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { Write-Host "Python 3.10+ is needed: https://www.python.org/downloads/" -ForegroundColor Red; exit 1 }
$node = Get-Command npm -ErrorAction SilentlyContinue
if (-not $node) { Write-Host "Node.js 18+ is needed: https://nodejs.org/" -ForegroundColor Red; exit 1 }

Set-Location "$root\backend"
if (-not (Test-Path ".venv")) {
  Write-Host "Creating Python environment..."
  python -m venv .venv
}
& ".\.venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt

Set-Location "$root\frontend"
if (-not (Test-Path "node_modules")) {
  Write-Host "Installing web app packages..."
  npm install --no-audit --no-fund
}
Write-Host "Building web app..."
npm run build

Set-Location "$root\backend"
Write-Host ""
Write-Host "NeuroTwin is starting at http://127.0.0.1:8000  (Ctrl+C to stop)" -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
