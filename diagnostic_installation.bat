@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo Diagnostic Valoria Vision V0.6.6-R6.1
echo ============================================================
echo.

if not exist .venv\Scripts\python.exe (
    echo .venv absent. Lance install.bat.
    pause
    exit /b 1
)

call .venv\Scripts\activate
python tools\diagnostic_installation.py
pause
