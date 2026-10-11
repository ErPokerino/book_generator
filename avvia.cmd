@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo.
echo  NarrAI — avvio locale
echo.

where uv >nul 2>&1
if errorlevel 1 (
  echo uv non trovato. Installa uv da https://github.com/astral-sh/uv
  pause
  exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
  echo npm non trovato. Installa Node.js 22.13 o successivo.
  pause
  exit /b 1
)

if not exist "backend\.venv\" (
  echo Prima esecuzione: sincronizzo le dipendenze Python...
  pushd "%~dp0backend"
  uv sync
  if errorlevel 1 (
    echo uv sync non riuscito.
    popd
    pause
    exit /b 1
  )
  popd
)

if not exist "frontend\node_modules\" (
  echo Prima esecuzione: installo le dipendenze npm...
  pushd "%~dp0frontend"
  call npm install
  if errorlevel 1 (
    echo npm install non riuscito.
    popd
    pause
    exit /b 1
  )
  popd
)

set "PORT_PLAN="
for /f "usebackq delims=" %%L in (`powershell -NoProfile -File "%~dp0scripts\resolve-api-port.ps1"`) do set "PORT_PLAN=%%L"

if "%PORT_PLAN%"=="fail" (
  echo Nessuna porta libera tra 8000 e 8020 per il backend.
  pause
  exit /b 1
)

for /f "tokens=1,2 delims=:" %%A in ("%PORT_PLAN%") do (
  set "PORT_MODE=%%A"
  set "API_PORT=%%B"
)

if "%PORT_MODE%"=="other" (
  echo La porta 8000 e' gia' usata da un'altra applicazione.
  echo Il backend NarrAI partira' sulla porta %API_PORT%.
) else if "%PORT_MODE%"=="reuse" (
  echo Backend NarrAI gia' in esecuzione sulla porta %API_PORT%.
) else (
  echo Avvio il backend sulla porta %API_PORT%.
)

echo  Backend   http://127.0.0.1:%API_PORT%
echo  Frontend  http://localhost:5173
echo.

if /I not "%PORT_MODE%"=="reuse" (
  start "NarrAI backend" /D "%~dp0backend" cmd /k uv run uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port %API_PORT%
)

start "NarrAI frontend" /D "%~dp0frontend" cmd /k "set NARRAI_API_TARGET=http://127.0.0.1:%API_PORT%&& npm run dev"

echo In attesa del frontend...
timeout /t 4 /nobreak >nul
start "" "http://localhost:5173"

endlocal

