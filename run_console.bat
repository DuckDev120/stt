@echo off
title Speech-to-Text Dictation Service (Console Mode)
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found! Please run install.bat first.
    pause
    exit /b 1
)

echo ======================================================================
echo Speech-to-Text Dictation Service - Console Mode
echo ======================================================================
echo Hotkeys: Right Alt / Fn / Apps (0x5D) / Right Ctrl
echo Acceleration: NVIDIA RTX 5060 Ti CUDA FP16
echo Keep this window open to view live logs, key events, and transcriptions.
echo ======================================================================
echo.

".venv\Scripts\python.exe" -m src.main
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [EXIT] Process stopped with code %ERRORLEVEL%.
    pause
)
