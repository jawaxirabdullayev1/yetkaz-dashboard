@echo off
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
chcp 65001 >nul
"%~dp0python\python.exe" bot.py
pause
