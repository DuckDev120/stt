@echo off
title Key Detection Utility
cd /d "%~dp0"
".venv\Scripts\python.exe" detect_key.py
pause
