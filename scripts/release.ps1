#Requires -Version 5.1
<#
.SYNOPSIS
    Bump version, build the installer, and push a release tag.

.DESCRIPTION
    1. Fetches tags from origin and finds the latest version tag
    2. Prompts for patch / minor / major bump (or pass a flag)
    3. Updates __version__ in budget_tracker/__init__.py
    4. Runs build.ps1 (unless -SkipBuild)
    5. Commits the version bump and tags the commit
    6. Pushes the commit and tag to origin

.PARAMETER Patch
    Bump the patch component: 1.2.3 -> 1.2.4

.PARAMETER Minor
    Bump the minor component: 1.2.3 -> 1.3.0

.PARAMETER Major
    Bump the major component: 1.2.3 -> 2.0.0

.PARAMETER SkipBuild
    Skip running build.ps1 (uses an existing dist/BudgetTracker-*-Setup.exe).

.EXAMPLE
    .\scripts\release.ps1
    Interactive: shows current version, prompts for bump type.

.EXAMPLE
    .\scripts\release.ps1 -Patch -SkipBuild
    Non-interactive patch bump, skip the build step.
#>
param(
    [switch]$Patch,
    [switch]$Minor,
    [switch]$Major,
    [switch]$SkipBuild
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root     = Split-Path -Parent $PSScriptRoot
$InitFile = Join-Path $Root "budget_tracker\__init__.py"

# ---------------------------------------------------------------------------
# Step 1 - Find the latest version tag (local + remote)
# ---------------------------------------------------------------------------
Write-Host "Fetching tags from origin..." -ForegroundColor Cyan
git fetch --tags --quiet

$LatestTag = git tag --sort=-v:refname 2>&1 |
             Where-Object { $_ -match '^v\d+\.\d+\.\d+$' } |
             Select-Object -First 1

if ($LatestTag) {
    $CurrentVersion = $LatestTag.TrimStart('v')
    Write-Host "Latest tag: $LatestTag" -ForegroundColor White
} else {
    # No tags yet: use the version in __init__.py as the baseline
    $vline = Get-Content $InitFile | Where-Object { $_ -match '__version__' } | Select-Object -First 1
    if ($vline -match '"([^"]+)"' -or $vline -match "'([^']+)'") {
        $CurrentVersion = $Matches[1]
    } else {
        $CurrentVersion = "0.0.0"
    }
    Write-Host "No version tags found. Using $CurrentVersion as baseline." -ForegroundColor Yellow
}

$parts   = $CurrentVersion -split '\.'
$Maj = [int]$parts[0]; $Min = [int]$parts[1]; $Pat = [int]$parts[2]

# ---------------------------------------------------------------------------
# Step 2 - Determine bump type
# ---------------------------------------------------------------------------
if (-not ($Patch -or $Minor -or $Major)) {
    Write-Host ""
    Write-Host "Current version: $CurrentVersion" -ForegroundColor White
    Write-Host "  [1] Patch  ->  $Maj.$Min.$($Pat + 1)"
    Write-Host "  [2] Minor  ->  $Maj.$($Min + 1).0"
    Write-Host "  [3] Major  ->  $($Maj + 1).0.0"
    $choice = Read-Host "Bump type [1/2/3]"
    switch ($choice.Trim()) {
        "1" { $Patch = $true }
        "2" { $Minor = $true }
        "3" { $Major = $true }
        default { Write-Error "Invalid choice. Aborting."; exit 1 }
    }
}

$NewVersion = if ($Major) { "$($Maj+1).0.0" }
              elseif ($Minor) { "$Maj.$($Min+1).0" }
              else { "$Maj.$Min.$($Pat+1)" }
$NewTag = "v$NewVersion"

Write-Host "`n$CurrentVersion  ->  $NewVersion  (tag: $NewTag)" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 3 - Guards
# ---------------------------------------------------------------------------
# Clean working tree required (we will make a commit ourselves)
$dirty = git status --porcelain 2>&1
if ($dirty) {
    Write-Error "Working tree has uncommitted changes. Commit or stash them first."
    exit 1
}

if (git tag -l $NewTag) {
    Write-Error "Tag $NewTag already exists locally. Delete it first: git tag -d $NewTag"
    exit 1
}

$remoteCheck = git ls-remote --tags origin "refs/tags/$NewTag" 2>&1
if ($remoteCheck -match [regex]::Escape($NewTag)) {
    Write-Error "Tag $NewTag already exists on origin."
    exit 1
}

# ---------------------------------------------------------------------------
# Step 4 - Update __version__ in __init__.py
# ---------------------------------------------------------------------------
$initContent = Get-Content $InitFile -Raw
$initContent = $initContent -replace `
    '__version__\s*=\s*["''][^"'']+["'']', `
    "__version__ = `"$NewVersion`""
[System.IO.File]::WriteAllText($InitFile, $initContent, (New-Object System.Text.UTF8Encoding $false))
Write-Host "Updated $InitFile" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 5 - Build
# ---------------------------------------------------------------------------
if (-not $SkipBuild) {
    Write-Host "`nRunning build.ps1..." -ForegroundColor Cyan
    & "$PSScriptRoot\build.ps1"
    if ($LASTEXITCODE -ne 0) {
        # Restore __init__.py so the repo is not left in a half-bumped state
        git checkout -- $InitFile
        Write-Error "build.ps1 failed. Reverted __init__.py."
        exit 1
    }
} else {
    Write-Host "`n[build] Skipped (-SkipBuild)" -ForegroundColor DarkGray
}

$SetupExe = Join-Path $Root "dist\BudgetTracker-$NewVersion-Setup.exe"
if (-not (Test-Path $SetupExe)) {
    git checkout -- $InitFile
    Write-Error "Setup exe not found: $SetupExe`nReverted __init__.py."
    exit 1
}
$SizeMB = [math]::Round((Get-Item $SetupExe).Length / 1MB, 1)
Write-Host "Asset:  $(Split-Path -Leaf $SetupExe)  ($SizeMB MB)" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 6 - Commit version bump and tag
# ---------------------------------------------------------------------------
Write-Host "`nCommitting version bump..." -ForegroundColor Cyan

# Stage only __init__.py (nothing else should be modified)
git add (Join-Path "budget_tracker" "__init__.py")
git commit -m "chore: bump version to $NewVersion"

git tag -a $NewTag -m "Release $NewVersion"
Write-Host "Tagged $NewTag" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 7 - Push commit + tag
# ---------------------------------------------------------------------------
Write-Host "`nPushing..." -ForegroundColor Cyan
git push origin HEAD
if ($LASTEXITCODE -ne 0) { Write-Error "git push (commit) failed."; exit 1 }

git push origin $NewTag
if ($LASTEXITCODE -ne 0) { Write-Error "git push (tag) failed."; exit 1 }

Write-Host "`nDone. Tag $NewTag is live on origin." -ForegroundColor Green
Write-Host "Installer: dist\BudgetTracker-$NewVersion-Setup.exe" -ForegroundColor White