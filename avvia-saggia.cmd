@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\avvia-saggia.ps1" %*
if errorlevel 1 pause
