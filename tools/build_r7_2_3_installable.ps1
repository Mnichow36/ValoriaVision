param(
    [string]$ReleaseName = "ValoriaVision_INSTALLABLE_V0_6_6_R7_2_3_IMPORTS_FIX"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

Write-Host "Valoria Vision — build installable R7.2.3 Imports Fix"
Write-Host "Dossier racine : $Root"

$ReleaseRoot = Join-Path $Root "release"
$ReleaseDir = Join-Path $ReleaseRoot $ReleaseName
$ZipPath = Join-Path $ReleaseRoot "$ReleaseName.zip"
$ShaPath = Join-Path $ReleaseRoot "$ReleaseName.sha256.txt"

if (Test-Path $ReleaseDir) { Remove-Item $ReleaseDir -Recurse -Force }
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
if (Test-Path $ShaPath) { Remove-Item $ShaPath -Force }
if (Test-Path (Join-Path $Root "build")) { Remove-Item (Join-Path $Root "build") -Recurse -Force }
if (Test-Path (Join-Path $Root "dist")) { Remove-Item (Join-Path $Root "dist") -Recurse -Force }
if (Test-Path (Join-Path $Root "Valoria Vision.spec")) { Remove-Item (Join-Path $Root "Valoria Vision.spec") -Force }

New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null

python -m pip install --upgrade pip
python -m pip install -r requirements-lock.txt

Write-Host "Compilation de contrôle Python..."
python -m compileall app tools main.py

Write-Host "Tests techniques R7.2 — imports..."
python tools/test_r7_2_import_sg.py
python tools/test_r7_2_false_duplicate_53.py
python tools/test_r7_2_import_report.py
python tools/test_r7_2_all_duplicate_import_message.py

Write-Host "Tests techniques R7.2 — Lot 3..."
python tools/test_r7_2_account_management.py
python tools/test_r7_2_reports_page.py

Write-Host "Build PyInstaller..."
$PlotlyRuntime = Join-Path $Root "data\runtime\plotly.min.js"
$PyInstallerArgs = @(
    "--noconfirm",
    "--windowed",
    "--name", "Valoria Vision",
    "--add-data", "$PlotlyRuntime;data/runtime",
    "main.py"
)
python -m PyInstaller @PyInstallerArgs

$AppDist = Join-Path $Root "dist\Valoria Vision"
if (!(Test-Path $AppDist)) {
    throw "Build PyInstaller introuvable : $AppDist"
}

Copy-Item $AppDist $ReleaseDir -Recurse -Force
Copy-Item (Join-Path $Root "LISEZMOI_R7_2_3_IMPORTS_FIX.txt") $ReleaseDir -Force
Copy-Item (Join-Path $Root "RELEASE_NOTES_R7_2_3_IMPORTS_FIX.md") $ReleaseDir -Force

$Manifest = @{
    product = "Valoria Vision"
    version = "V0.6.6-R7.2.3 Imports Fix"
    release_name = $ReleaseName
    branch = "dev/r7.2-cdc-v1.1-imports-rapprochements"
    build_date_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    scope = "Imports bancaires, transactions, faux doublon SG #53, rapport d'import automatique, réimport 100% doublon, Lot 3 comptes RIB/IBAN, progression import, rapports centralisés"
    executable = "Valoria Vision/Valoria Vision.exe"
    status = "Version intermédiaire de recette"
}
$Manifest | ConvertTo-Json -Depth 4 | Out-File -FilePath (Join-Path $ReleaseDir "manifest_r7_2_3.json") -Encoding utf8

Compress-Archive -Path (Join-Path $ReleaseDir "*") -DestinationPath $ZipPath -Force
$Hash = Get-FileHash $ZipPath -Algorithm SHA256
"$($Hash.Hash)  $ReleaseName.zip" | Out-File -FilePath $ShaPath -Encoding ascii

Write-Host ""
Write-Host "Build terminé."
Write-Host "Archive : $ZipPath"
Write-Host "SHA-256 : $($Hash.Hash)"
