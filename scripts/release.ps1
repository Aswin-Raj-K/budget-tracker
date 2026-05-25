#Requires -Version 5.1
<#
.SYNOPSIS
    Build and publish a GitHub release for Budget Tracker.

.DESCRIPTION
    1. Reads the version from budget_tracker/__init__.py
    2. Runs build.ps1 to produce the installer (unless -SkipBuild)
    3. Creates and pushes an annotated git tag  v<version>
    4. Creates a GitHub release via the gh CLI with the setup exe as the asset

.PARAMETER SkipBuild
    Skip running build.ps1. Expects dist/BudgetTracker-<version>-Setup.exe to
    already exist (useful when you just want to re-publish a build).

.PARAMETER Draft
    Create the release as a draft so you can review and edit it on GitHub
    before it goes public.

.PARAMETER Prerelease
    Mark the release as a pre-release (alpha/beta/rc).

.PARAMETER Notes
    Release body text. If omitted, GitHub auto-generates notes from commits
    since the previous tag.

.EXAMPLE
    .\scripts\release.ps1
    Build + tag + publish.

.EXAMPLE
    .\scripts\release.ps1 -SkipBuild -Draft
    Publish an already-built installer as a draft release.
#>
param(
    [switch]$SkipBuild,
    [switch]$Draft,
    [switch]$Prerelease,
    [string]$Notes = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot

# ---------------------------------------------------------------------------
# Step 1 — Read version
# ---------------------------------------------------------------------------
$InitFile    = Join-Path $Root "budget_tracker\__init__.py"
$VersionLine = Get-Content $InitFile |
               Where-Object { $_ -match '__version__' } |
               Select-Object -First 1

if ($VersionLine -match '"([^"]+)"' -or $VersionLine -match "'([^']+)'") {
    $AppVersion = $Matches[1]
} else {
    Write-Error "Cannot parse __version__ from $InitFile"
    exit 1
}

$Tag = "v$AppVersion"
Write-Host "Release: Budget Tracker $AppVersion  (tag: $Tag)" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# Step 2 — Verify prerequisites
# ---------------------------------------------------------------------------
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error @"
GitHub CLI (gh) not found.
Install it from https://cli.github.com and run 'gh auth login' once.
"@
    exit 1
}

# Ensure we are authenticated
$null = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Not authenticated with gh. Run: gh auth login"
    exit 1
}

# ---------------------------------------------------------------------------
# Step 3 — Guard: no dirty working tree, tag must be new
# ---------------------------------------------------------------------------
$dirty = git status --porcelain 2>&1
if ($dirty) {
    Write-Warning "Working tree has uncommitted changes:"
    Write-Host $dirty -ForegroundColor Yellow
    $ans = Read-Host "Continue anyway? [y/N]"
    if ($ans -notmatch '^[Yy]') { exit 1 }
}

$existingTag = git tag -l $Tag
if ($existingTag) {
    Write-Error @"
Tag $Tag already exists locally.
If you want to re-release the same version, delete the tag first:
  git tag -d $Tag && git push origin :refs/tags/$Tag
Or bump __version__ in budget_tracker/__init__.py.
"@
    exit 1
}

# Check remote too (avoids a push failure later)
$remoteTags = git ls-remote --tags origin "refs/tags/$Tag" 2>&1
if ($remoteTags -match $Tag) {
    Write-Error "Tag $Tag already exists on origin. Bump __version__ or delete the remote tag first."
    exit 1
}

# ---------------------------------------------------------------------------
# Step 4 — Build
# ---------------------------------------------------------------------------
if (-not $SkipBuild) {
    Write-Host "`nRunning build.ps1…" -ForegroundColor Cyan
    & "$PSScriptRoot\build.ps1"
    if ($LASTEXITCODE -ne 0) { Write-Error "build.ps1 failed — aborting release."; exit 1 }
} else {
    Write-Host "`n[build] Skipped (-SkipBuild)" -ForegroundColor DarkGray
}

# ---------------------------------------------------------------------------
# Step 5 — Verify setup exe
# ---------------------------------------------------------------------------
$SetupExe = Join-Path $Root "dist\BudgetTracker-$AppVersion-Setup.exe"
if (-not (Test-Path $SetupExe)) {
    Write-Error @"
Setup exe not found: $SetupExe
Run build.ps1 first, or omit -SkipBuild.
"@
    exit 1
}
$SizeMB = [math]::Round((Get-Item $SetupExe).Length / 1MB, 1)
Write-Host "`nAsset: $(Split-Path -Leaf $SetupExe)  ($SizeMB MB)" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 6 — Create and push the git tag
# ---------------------------------------------------------------------------
Write-Host "`nTagging commit as $Tag…" -ForegroundColor Cyan
git tag -a $Tag -m "Release $AppVersion"
git push origin $Tag
if ($LASTEXITCODE -ne 0) {
    # Roll back local tag so the script can be re-run cleanly
    git tag -d $Tag | Out-Null
    Write-Error "git push tag failed — local tag removed. Fix the push issue and retry."
    exit 1
}
Write-Host "      Tag pushed." -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 7 — Create GitHub release
# ---------------------------------------------------------------------------
Write-Host "`nCreating GitHub release…" -ForegroundColor Cyan

$ghArgs = @(
    "release", "create", $Tag,
    $SetupExe,
    "--title", "Budget Tracker $AppVersion"
)

if ($Draft)      { $ghArgs += "--draft" }
if ($Prerelease) { $ghArgs += "--prerelease" }

if ($Notes) {
    $ghArgs += "--notes"
    $ghArgs += $Notes
} else {
    $ghArgs += "--generate-notes"
}

$ReleaseUrl = gh @ghArgs
if ($LASTEXITCODE -ne 0) {
    Write-Error "gh release create failed. The tag $Tag was pushed — delete it manually if you need to retry: git push origin :refs/tags/$Tag"
    exit 1
}

Write-Host "`nDone." -ForegroundColor Green
if ($Draft) {
    Write-Host "Draft release (not yet public): $ReleaseUrl" -ForegroundColor Yellow
} else {
    Write-Host "Published: $ReleaseUrl" -ForegroundColor Cyan
}
