Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Avvio backend in dev con reload limitato ai soli file di codice (evita reload quando genera PDF/cover)
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "Starting backend (safe reload) on http://127.0.0.1:8000 ..."
uv run uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8000

