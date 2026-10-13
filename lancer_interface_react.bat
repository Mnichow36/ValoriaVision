@echo off
setlocal
cd /d "%~dp0"
title Valoria Vision - Lancement React

echo.
echo ========================================
echo   Valoria Vision - Interface React
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creation de l'environnement Python...
    py -m venv .venv || goto :error
    echo [2/4] Installation des dependances Python...
    call ".venv\Scripts\python.exe" -m pip install -r requirements.txt -r requirements-react-api.txt || goto :error
) else (
    echo [1/4] Environnement Python detecte.
    ".venv\Scripts\python.exe" -c "import fastapi, uvicorn" >nul 2>&1
    if errorlevel 1 (
        echo [2/4] Installation des dependances de l'API...
        call ".venv\Scripts\python.exe" -m pip install -r requirements-react-api.txt || goto :error
    ) else (
        echo [2/4] Dependances de l'API disponibles.
    )
)

if not exist "frontend\node_modules\.bin\vite.cmd" (
    echo [3/4] Installation des dependances React...
    pushd frontend
    call npm.cmd install || goto :npm_error
    popd
) else (
    echo [3/4] Dependances React disponibles.
)

echo [4/4] Demarrage des deux services...
start "Valoria Vision - Moteur Python" /D "%~dp0" cmd /k ".venv\Scripts\python.exe -m app.api.run"
start "Valoria Vision - Interface React" /D "%~dp0frontend" cmd /k "npm.cmd run dev"

timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:5173/"

echo.
echo Deux fenetres ont ete ouvertes :
echo - Valoria Vision - Moteur Python
echo - Valoria Vision - Interface React
echo.
echo Laissez ces deux fenetres ouvertes pendant l'utilisation.
timeout /t 4 /nobreak >nul
exit /b 0

:npm_error
popd

:error
echo.
echo Le lancement a echoue. Conservez cette fenetre et copiez le message d'erreur.
pause
exit /b 1
