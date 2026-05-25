#Requires -Version 5.1
<#
.SYNOPSIS
    Build the Budget Tracker Windows installer.

.DESCRIPTION
    Step 1: Read version from budget_tracker/__init__.py
    Step 2: Bundle the app with PyInstaller  (dist/Budget Tracker/)
    Step 3: Zip the app bundle               (build/app_bundle.zip)
    Step 4: Build the uninstaller exe        (build/uninstaller/BudgetTrackerUninstall.exe)
    Step 5: Write _installer_version.py      (embeds version into wizard)
    Step 6: Build the installer exe          (dist/BudgetTracker-<ver>-Setup.exe)

.PARAMETER SkipApp
    Skip Steps 2-3 (app bundle). Useful when iterating on the installer UI.

.PARAMETER SkipInstaller
    Skip Steps 4-6 (installer build).
#>
param(
    [switch]$SkipApp,
    [switch]$SkipInstaller
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root          = Split-Path -Parent $PSScriptRoot
$InstallerSrc  = Join-Path $Root "installer_src"
$BuildDir      = Join-Path $Root "build"
$DistDir       = Join-Path $Root "dist"

# ---------------------------------------------------------------------------
# Step 1 - Read version
# ---------------------------------------------------------------------------
$InitFile    = Join-Path $Root "budget_tracker\__init__.py"
$VersionLine = Get-Content $InitFile | Where-Object { $_ -match '__version__' } | Select-Object -First 1
if ($VersionLine -match '"([^"]+)"' -or $VersionLine -match "'([^']+)'") {
    $AppVersion = $Matches[1]
} else {
    Write-Error "Cannot parse __version__ from $InitFile"
    exit 1
}
Write-Host "Building Budget Tracker $AppVersion" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# Step 2 - Bundle the app with PyInstaller
# ---------------------------------------------------------------------------
if (-not $SkipApp) {
    Write-Host "`n[2/6] Bundling app with PyInstaller..." -ForegroundColor Cyan
    Push-Location $Root
    pyinstaller budget_tracker.spec --clean --noconfirm
    if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Error "PyInstaller (app) failed"; exit 1 }
    Pop-Location
    Write-Host "      => dist\Budget Tracker\" -ForegroundColor Green
} else {
    Write-Host "`n[2/6] Skipped (SkipApp)" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# Step 3 - Zip the app bundle
# ---------------------------------------------------------------------------
if (-not $SkipApp) {
    Write-Host "`n[3/6] Zipping app bundle..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Force $BuildDir | Out-Null
    $AppBundleZip = Join-Path $BuildDir "app_bundle.zip"
    # Use Python's zipfile instead of Compress-Archive -- Python opens files
    # with shared read access so it handles locked files (base_library.zip,
    # AV scans) that Compress-Archive chokes on.
    python -c @"
import zipfile, sys
from pathlib import Path
src = Path(r'$DistDir\Budget Tracker')
dst = Path(r'$AppBundleZip')
dst.unlink(missing_ok=True)
with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for f in sorted(src.rglob('*')):
        if f.is_file():
            zf.write(f, f.relative_to(src))
print(f'Zipped {dst.stat().st_size // 1024 // 1024} MB')
"@
    if ($LASTEXITCODE -ne 0) { Write-Error "Zip step failed"; exit 1 }
    Write-Host "      => build\app_bundle.zip" -ForegroundColor Green
} else {
    Write-Host "`n[3/6] Skipped (SkipApp)" -ForegroundColor DarkGray
}

if (-not $SkipInstaller) {
    # -------------------------------------------------------------------------
    # Step 4 - Build the uninstaller
    # -------------------------------------------------------------------------
    Write-Host "`n[4/6] Building uninstaller..." -ForegroundColor Cyan
    Push-Location $InstallerSrc
    pyinstaller uninstaller.spec --clean --noconfirm
    if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Error "PyInstaller (uninstaller) failed"; exit 1 }
    Pop-Location

    $UninstallerDestDir = Join-Path $BuildDir "uninstaller"
    New-Item -ItemType Directory -Force $UninstallerDestDir | Out-Null
    $UninstallerSrc  = Join-Path $InstallerSrc "dist\BudgetTrackerUninstall.exe"
    $UninstallerDest = Join-Path $UninstallerDestDir "BudgetTrackerUninstall.exe"
    if (Test-Path $UninstallerDest) { Remove-Item $UninstallerDest -Force }
    Move-Item $UninstallerSrc $UninstallerDest
    Write-Host "      => build\uninstaller\BudgetTrackerUninstall.exe" -ForegroundColor Green

    # -------------------------------------------------------------------------
    # Step 5 - Write _installer_version.py (read by the wizard at runtime)
    # -------------------------------------------------------------------------
    Write-Host "`n[5/6] Writing installer version module..." -ForegroundColor Cyan
    $VersionModule = Join-Path $InstallerSrc "_installer_version.py"
    "APP_VERSION = `"$AppVersion`"" | Out-File -FilePath $VersionModule -Encoding utf8 -NoNewline
    Write-Host "      => installer_src\_installer_version.py" -ForegroundColor Green

    # -------------------------------------------------------------------------
    # Step 6 - Build the installer
    # -------------------------------------------------------------------------
    Write-Host "`n[6/6] Building installer..." -ForegroundColor Cyan
    Push-Location $InstallerSrc
    pyinstaller installer.spec --clean --noconfirm
    if ($LASTEXITCODE -ne 0) { Pop-Location; Write-Error "PyInstaller (installer) failed"; exit 1 }
    Pop-Location

    $SetupSrc  = Join-Path $InstallerSrc "dist\BudgetTrackerSetup.exe"
    $SetupDest = Join-Path $DistDir "BudgetTracker-$AppVersion-Setup.exe"
    New-Item -ItemType Directory -Force $DistDir | Out-Null
    if (Test-Path $SetupDest) { Remove-Item $SetupDest -Force }
    Move-Item $SetupSrc $SetupDest
    Write-Host "      => dist\BudgetTracker-$AppVersion-Setup.exe" -ForegroundColor Green
} else {
    Write-Host "`n[4-6/6] Skipped (SkipInstaller)" -ForegroundColor DarkGray
}

Write-Host "`nBuild complete." -ForegroundColor Green
if (-not $SkipInstaller) {
    Write-Host "Installer: dist\BudgetTracker-$AppVersion-Setup.exe" -ForegroundColor White
}