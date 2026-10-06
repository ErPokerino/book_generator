param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskBackend = Join-Path $taskRoot 'backend'
$taskFrontend = Join-Path $taskRoot 'frontend'
$taskLogs = Join-Path $taskBackend 'data\saggistica\logs'
New-Item -ItemType Directory -Path $taskLogs -Force | Out-Null
$taskPython = Join-Path $taskBackend '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) {
    Push-Location $taskBackend
    try { & uv sync --locked; if ($LASTEXITCODE -ne 0) { throw 'Installazione backend non riuscita.' } } finally { Pop-Location }
}
if (-not (Test-Path -LiteralPath (Join-Path $taskFrontend 'node_modules\vite\bin\vite.js'))) {
    Push-Location $taskFrontend
    try { & npm ci; if ($LASTEXITCODE -ne 0) { throw 'Installazione frontend non riuscita.' } } finally { Pop-Location }
}
function Test-SaggiaBackend {
    try { return (Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/health' -TimeoutSec 2).product -eq 'saggia' } catch { return $false }
}
if (-not (Test-SaggiaBackend)) {
    if (Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue) { throw 'La porta 8001 e occupata da un altro servizio.' }
    Start-Process -FilePath $taskPython -ArgumentList '-m','uvicorn','app.essay.main:app','--host','127.0.0.1','--port','8001' -WorkingDirectory $taskBackend -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskLogs 'backend.stdout.log') -RedirectStandardError (Join-Path $taskLogs 'backend.stderr.log') | Out-Null
}
$taskReady = $false
for ($taskAttempt = 0; $taskAttempt -lt 45; $taskAttempt++) {
    if (Test-SaggiaBackend) { $taskReady = $true; break }
    Start-Sleep -Milliseconds 500
}
if (-not $taskReady) { throw "Il backend non risponde. Controlla $taskLogs\backend.stderr.log" }
$taskFrontReady = $false
try {
    $taskPage = Invoke-WebRequest -Uri 'http://127.0.0.1:5174/' -UseBasicParsing -TimeoutSec 2
    $taskFrontReady = $taskPage.Content.Contains('<title>SaggIA</title>')
} catch {}
if (-not $taskFrontReady) {
    if (Get-NetTCPConnection -LocalPort 5174 -State Listen -ErrorAction SilentlyContinue) { throw 'La porta 5174 e occupata da un altro servizio.' }
    $taskNode = (Get-Command node -ErrorAction Stop).Source
    $taskVite = '"' + (Join-Path $taskFrontend 'node_modules\vite\bin\vite.js') + '"'
    Start-Process -FilePath $taskNode -ArgumentList $taskVite -WorkingDirectory $taskFrontend -WindowStyle Hidden -RedirectStandardOutput (Join-Path $taskLogs 'frontend.stdout.log') -RedirectStandardError (Join-Path $taskLogs 'frontend.stderr.log') | Out-Null
    for ($taskAttempt = 0; $taskAttempt -lt 30; $taskAttempt++) {
        try { $taskPage=Invoke-WebRequest -Uri 'http://127.0.0.1:5174/' -UseBasicParsing -TimeoutSec 2; if ($taskPage.Content.Contains('<title>SaggIA</title>')) { $taskFrontReady=$true; break } } catch {}
        Start-Sleep -Milliseconds 500
    }
}
if (-not $taskFrontReady) { throw "Il frontend non risponde. Controlla $taskLogs\frontend.stderr.log" }
Write-Host 'SaggIA pronta: http://127.0.0.1:5174'
Write-Host "Archivio e log: $taskBackend\data\saggistica"
if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:5174' }
