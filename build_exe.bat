@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\activate (
    echo Environnement virtuel absent. Lancez d'abord install.bat
    pause
    exit /b 1
)
call .venv\Scripts\activate
python -m pip install --upgrade pyinstaller
pyinstaller --noconfirm --windowed --name Valoria Vision main.py

echo.
echo Build termine.
echo Executable : dist\Valoria Vision\Valoria Vision.exe
echo.
pause
