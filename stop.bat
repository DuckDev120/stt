@echo off
title Stop Speech-to-Text Dictation Service
cd /d "%~dp0"

echo Stopping any running Speech-to-Text instances...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*src.main*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo [OK] All Speech-to-Text background instances stopped.
ping 127.0.0.1 -n 2 >nul
exit /b 0
