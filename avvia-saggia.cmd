@echo off
setlocal EnableExtensions
set "SAGGIA_LAUNCHER=%~dp0avvia.cmd"
if not exist "%SAGGIA_LAUNCHER%" (
  echo Impossibile trovare l'avvio di NarrAI, che ora include i saggi.
  echo Percorso previsto: %SAGGIA_LAUNCHER%
  pause
  exit /b 1
)
call "%SAGGIA_LAUNCHER%" %*
exit /b %errorlevel%
