@echo off
setlocal
cd /d "%~dp0"

echo ============================================================
echo Installation Valoria Vision V0.6.6-R6.1
echo Base consolidée installable
echo ============================================================
echo.
echo Cette installation cree ou repare .venv avec des versions verrouillees.
echo Elle installe notamment PySide6, Plotly et cryptography.
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
)

echo Activation de .venv...
call .venv\Scripts\activate

echo Mise a jour de pip...
python -m pip install --upgrade pip

echo Installation / reparation des dependances verrouillees...
pip install -r requirements-lock.txt
if errorlevel 1 (
    echo.
    echo ERREUR : installation des dependances impossible.
    pause
    exit /b 1
)

echo Verification des modules critiques...
python -c "import PySide6, plotly, cryptography; print('OK PySide6', PySide6.__version__); print('OK Plotly', plotly.__version__); print('OK cryptography', cryptography.__version__)"
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
