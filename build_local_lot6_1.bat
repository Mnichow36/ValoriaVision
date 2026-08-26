@echo off
setlocal

cd /d "%~dp0"

echo ============================================================
echo Valoria Vision - Build local Lot 6.1 Scenarios parametrables
echo ============================================================
echo.

if not exist "tools\build_r7_2_3_installable.ps1" (
  echo ERREUR : script PowerShell introuvable.
  echo Fichier attendu : tools\build_r7_2_3_installable.ps1
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "tools\build_r7_2_3_installable.ps1"
set BUILD_ERROR=%ERRORLEVEL%

if not "%BUILD_ERROR%"=="0" (
  echo.
  echo ERREUR : le build local a echoue. Code : %BUILD_ERROR%
  pause
  exit /b %BUILD_ERROR%
)

echo.
echo Build local Lot 6.1 termine.
if exist "release" (
  start "" "%CD%\release"
) else (
  start "" "%CD%"
)

pause
