# Contact Center QA POC — dev runner (Windows PowerShell)
# Creates a venv if needed, installs deps, and starts the app.

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment (.venv)..." -ForegroundColor Cyan
    python -m venv .venv
}

Write-Host "Installing dependencies..." -ForegroundColor Cyan
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip | Out-Null
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host "Starting Contact Center QA POC on http://localhost:8000 ..." -ForegroundColor Green
Write-Host "Backend traces stream here. Frontend traces: open the browser DevTools Console (F12)." -ForegroundColor DarkGray
& ".\.venv\Scripts\python.exe" -m uvicorn backend.main:app --reload --port 8000 --log-level debug
