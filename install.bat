@echo off
setlocal
cd /d "%~dp0"

set "PYTHONUTF8=1"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"

echo ============================================================
echo Installation Valoria Vision V0.6.6-R7.2.2.1.1
echo Correctif installation pip / dependances verrouillees
echo ============================================================
echo.
echo Cette installation cree ou repare .venv avec des versions verrouillees.
echo Elle installe notamment PySide6, Plotly, cryptography et openpyxl.
echo.

where py >nul 2>nul
if errorlevel 1 (
   echo ERREUR : Python n'a pas ete trouve avec le lanceur py.
   echo Installe Python 3 puis relance ce fichier.
    pause
    exit /b 1
)

if not exist .venv\Scripts\python.exe (
   echo Creation de l'environnement .venv...
    py -3 -m venv .venv
    if errorlevel 1 (
       echo.
       echo ERREUR : creation de .venv impossible.
        pause
        exit /b 1
    )
)

echo Verification de Python dans .venv...
.venv\Scripts\python.exe --version
if errorlevel 1 (
   echo.
   echo ERREUR : .venv existe mais Python ne demarre pas.
   echo Supprime le dossier .venv puis relance install.bat.
    pause
    exit /b 1
)

echo Mise a jour de pip...
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 (
   echo.
   echo ERREUR : mise a jour de pip impossible.
    pause
    exit /b 1
)

echo Installation / reparation des dependances verrouillees...
.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
if errorlevel 1 (
   echo.
   echo ERREUR : installation des dependances impossible.
   echo Conseil : supprime le dossier .venv puis relance install.bat.
    pause
    exit /b 1
)

echo Verification des modules critiques...
.venv\Scripts\python.exe -c "import PySide6, plotly, cryptography, openpyxl; print('OK PySide6', PySide6.__version__); print('OK Plotly', plotly.__version__); print('OK cryptography', cryptography.__version__); print('OK openpyxl', openpyxl.__version__)"
if errorlevel 1 (
   echo.
   echo ERREUR : au moins un module critique manque.
    pause
    exit /b 1
)

echo Verification Plotly local...
if not exist data\runtime\plotly.min.js (
   echo Le fichier data\runtime\plotly.min.js manque.
   echo Il sera regenere par l'application au premier lancement si possible.
) else (
   echo OK : data\runtime\plotly.min.js present.
)

echo.
echo Installation terminee.
echo Tu peux maintenant lancer run.bat
echo.
pause
