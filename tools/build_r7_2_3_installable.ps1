param(
    [string]$ReleaseName = "ValoriaVision_INSTALLABLE_V0_6_6_R7_2_4_LOT6_1_SCENARIOS_PARAMETRABLES"
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$BuildStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$EffectiveReleaseName = $ReleaseName + "_" + $BuildStamp

Write-Host "Valoria Vision - build installable R7.2.4 Lot 6.1 scenarios parametrables"
Write-Host ("Dossier racine : " + $Root)
Write-Host ("Release locale : " + $EffectiveReleaseName)

$ReleaseRoot = Join-Path $Root "release"
$ReleaseDir = Join-Path $ReleaseRoot $EffectiveReleaseName
$ZipPath = Join-Path $ReleaseRoot ($EffectiveReleaseName + ".zip")
$ShaPath = Join-Path $ReleaseRoot ($EffectiveReleaseName + ".sha256.txt")

$BuildRoot = Join-Path $Root ("build_local_" + $BuildStamp)
$PyBuildDir = Join-Path $BuildRoot "build"
$PyDistDir = Join-Path $BuildRoot "dist"
$PySpecDir = Join-Path $BuildRoot "spec"

New-Item -ItemType Directory -Path $ReleaseDir -Force | Out-Null
New-Item -ItemType Directory -Path $PyBuildDir -Force | Out-Null
New-Item -ItemType Directory -Path $PyDistDir -Force | Out-Null
New-Item -ItemType Directory -Path $PySpecDir -Force | Out-Null

# Ne pas supprimer les anciens dossiers build/dist/release : ils peuvent être
# verrouillés par Windows, OneDrive, l'antivirus ou une ancienne instance de
# Valoria Vision. Chaque build utilise désormais un dossier horodaté isolé.

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

Write-Host "Tests techniques R7.2 - Lot 5.3 sauvegarde..."
python tools/test_r7_2_complete_encrypted_backup.py

Write-Host "Tests techniques R7.2 - Lot 6.1 scenarios..."
python tools/test_r7_2_scenario_hypotheses.py

Write-Host "Build PyInstaller..."
$PlotlyRuntime = Join-Path $Root "data\runtime\plotly.min.js"
$PyInstallerArgs = @(
    "--noconfirm",
    "--windowed",
    "--name", "Valoria Vision",
    "--distpath", $PyDistDir,
    "--workpath", $PyBuildDir,
    "--specpath", $PySpecDir,
    "--add-data", ($PlotlyRuntime + ";data/runtime"),
    "main.py"
)
python -m PyInstaller @PyInstallerArgs

$AppDist = Join-Path $PyDistDir "Valoria Vision"
if (!(Test-Path $AppDist)) {
    throw ("Build PyInstaller introuvable : " + $AppDist)
}

Copy-Item $AppDist $ReleaseDir -Recurse -Force
Copy-Item (Join-Path $Root "LISEZMOI_R7_2_3_IMPORTS_FIX.txt") $ReleaseDir -Force
Copy-Item (Join-Path $Root "RELEASE_NOTES_R7_2_3_IMPORTS_FIX.md") $ReleaseDir -Force

$Manifest = @{
    product = "Valoria Vision"
    version = "V0.6.6-R7.2.4 Lot 6.1 Scenarios parametrables"
    release_name = $EffectiveReleaseName
    branch = "dev/r7.2.4-lot6-scenarios-parametrables"
    build_date_utc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    scope = "Lot 6.1 : hypotheses chiffrees Prudent / Realiste / Optimiste et impact reel sur les recurrents du previsionnel"
    executable = "Valoria Vision/Valoria Vision.exe"
    status = "Archive locale de recette Lot 6.1"
    local_build_strategy = "Dossiers horodates pour eviter les fichiers dist verrouilles"
}
$Manifest | ConvertTo-Json -Depth 4 | Out-File -FilePath (Join-Path $ReleaseDir "manifest_r7_2_4_lot6_1.json") -Encoding utf8

Compress-Archive -Path (Join-Path $ReleaseDir "*") -DestinationPath $ZipPath -Force
$Hash = Get-FileHash $ZipPath -Algorithm SHA256
$HashLine = $Hash.Hash + "  " + $EffectiveReleaseName + ".zip"
$HashLine | Out-File -FilePath $ShaPath -Encoding ascii

Write-Host ""
Write-Host "Build termine."
Write-Host ("Dossier : " + $ReleaseDir)
Write-Host ("Archive : " + $ZipPath)
Write-Host ("SHA-256 : " + $Hash.Hash)
