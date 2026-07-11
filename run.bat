@echo off
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
    echo Environnement .venv absent.
    echo Lance d'abord install.bat
    pause
    exit /b 1
)

call .venv\Scripts\activate
python main.py
pause
