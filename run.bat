@echo off
title Speech-to-Text Dictation Service
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found! Please run install.bat first.
    pause
    exit /b 1
)

echo Starting Speech-to-Text Dictation Studio - Control Center...
echo Hotkeys: Right Alt / Fn / Apps (VK_APPS) / Right Ctrl
start "" "%~dp0.venv\Scripts\pythonw.exe" -m src.main
exit /b 0
