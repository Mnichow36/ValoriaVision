@echo off
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\activate (
    echo Environnement virtuel absent. Lancez d'abord install.bat
    pause
    exit /b 1
)

call .venv\Scripts\activate
powershell -ExecutionPolicy Bypass -File tools\build_r7_2_3_installable.ps1

echo.
echo Build R7.2.3 termine.
echo Archive disponible dans le dossier release.
echo.
pause
