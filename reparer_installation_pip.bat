@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo Reparation installation pip - Valoria Vision R7.2.2.1
echo ============================================================
echo.
echo Ce script corrige l'installation si l'ancien install.bat a echoue avec :
echo "To modify pip, please run python.exe -m pip ..."
echo.

if exist .venv\Scripts\python.exe (
    echo Suppression de l'ancien environnement .venv incomplet...
    rmdir /s /q .venv
)

call install.bat
