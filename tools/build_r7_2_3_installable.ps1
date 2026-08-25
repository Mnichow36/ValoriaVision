param(
    [string]$ReleaseName = "ValoriaVision_INSTALLABLE_V0_6_6_R7_2_4_LOT5_2_UX_PREVISIONNEL"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

Write-Host "Valoria Vision - build installable R7.2.4 Lot 5.2 UX Previsionnel"
Write-Host ("Dossier racine : " + $Root)

$ReleaseRoot = Join-Path $Root "release"
$ReleaseDir = Join-Path $ReleaseRoot $ReleaseName
$ZipPath = Join-Path $ReleaseRoot ($ReleaseName + ".zip")
$ShaPath = Join-Path $ReleaseRoot ($ReleaseName + ".sha256.txt")

if (Test-Path $ReleaseDir) { Remove-Item $ReleaseDir -Recurse -Force }
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
if (Test-Path $ShaPath) { Remove-Item $ShaPath -Force }
if (Test-Path (Join-Path $Root "build")) { Remove-Item (Join-Path $Root "build") -Recurse -Force }
if (Test-Path (Join-Path $Root "dist")) { Remove-Item (Join-Path $Root "dist") -Recurse -Force }
if (Test-Path (Join-Path $Root "Valoria Vision.spec")) { Remove-Item (Join-Path $Root "Valoria Vision.spec") -Force }

New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null

python -m pip install --upgrade pip
python -m pip install -r requirements-lock.txt

Write-Host "Compilation de controle Python..."
python -m compileall app tools main.py

Write-Host "Tests techniques R7.2 - imports..."
python tools/test_r7_2_import_sg.py
python tools/test_r7_2_false_duplicate_53.py
python tools/test_r7_2_import_report.py
python tools/test_r7_2_all_duplicate_import_message.py

Write-Host "Tests techniques R7.2 - Lot 3..."
python tools/test_r7_2_account_management.py
python tools/test_r7_2_account_resolution.py
python tools/test_r7_2_reports_page.py

Write-Host "Tests techniques R7.2 - Lot 4..."
python tools/test_r7_2_import_lifecycle.py

Write-Host "Tests techniques R7.2 - Lot 5..."
python tools/test_r7_2_forecast_recurrences.py

Write-Host "Build PyInstaller..."
$PlotlyRuntime = Join-Path $Root "data\runtime\plotly.min.js"
$PyInstallerArgs = @(
    "--noconfirm",
    "--windowed",
    "--name", "Valoria Vision",
    "--add-data", ($PlotlyRuntime + ";data/runtime"),
    "main.py"
)
python -m PyInstaller @PyInstallerArgs

$AppDist = Join-Path $Root "dist\Valoria Vision"
if (!(Test-Path $AppDist)) {
    throw ("Build PyInstaller introuvable : " + $AppDist)
}

Copy-Item $AppDist $ReleaseDir -Recurse -Force
Copy-Item (Join-Path $Root "LISEZMOI_R7_2_3_IMPORTS_FIX.txt") $ReleaseDir -Force
Copy-Item (Join-Path $Root "RELEASE_NOTES_R7_2_3_IMPORTS_FIX.md") $ReleaseDir -Force

$Manifest = @{
    product = "Valoria Vision"
    version = "V0.6.6-R7.2.4 Lot 5.2 UX Previsionnel"
    release_name = $ReleaseName
    branch = "dev/r7.2-cdc-v1.1-imports-rapprochements"
    build_date_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    scope = "UX previsionnel : bouton ajout global retire, menu contextuel courbe simplifie, gestion recurrences conservee"
    executable = "Valoria Vision/Valoria Vision.exe"
    status = "Archive locale de recette Lot 5.2"
}
$Manifest | ConvertTo-Json -Depth 4 | Out-File -FilePath (Join-Path $ReleaseDir "manifest_r7_2_4_lot5_2.json") -Encoding utf8

Compress-Archive -Path (Join-Path $ReleaseDir "*") -DestinationPath $ZipPath -Force
$Hash = Get-FileHash $ZipPath -Algorithm SHA256
$HashLine = $Hash.Hash + "  " + $ReleaseName + ".zip"
$HashLine | Out-File -FilePath $ShaPath -Encoding ascii

Write-Host ""
Write-Host "Build termine."
Write-Host ("Archive : " + $ZipPath)
Write-Host ("SHA-256 : " + $Hash.Hash)
