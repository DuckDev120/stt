@echo off
setlocal enabledelayedexpansion
title Setup Speech-to-Text Dictation Service
cd /d "%~dp0"

echo =========================================================
echo  Installing Speech-to-Text Dictation Service
echo  RTX GPU Accelerated + Hebrew & English Dictation
echo =========================================================
echo.

where py >nul 2>nul
if %errorlevel% equ 0 (
    echo [*] Checking Python 3.12 launcher...
    py -3.12 --version >nul 2>nul
    if %errorlevel% equ 0 (
        set "PY_CMD=py -3.12"
    ) else (
        set "PY_CMD=python"
    )
) else (
    set "PY_CMD=python"
)

echo [*] Using: !PY_CMD!
echo [*] Creating virtual environment (.venv)...
!PY_CMD! -m venv .venv
if %errorlevel% neq 0 (
    echo [ERROR] Failed to create virtual environment!
    pause
    exit /b 1
)

echo [*] Upgrading pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip

echo [*] Installing dependencies from requirements.txt...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies!
    pause
    exit /b 1
)

echo.
echo =========================================================
echo  [SUCCESS] Installation completed successfully!
echo  Run "run.bat" to start the background service.
echo =========================================================
pause
exit /b 0
