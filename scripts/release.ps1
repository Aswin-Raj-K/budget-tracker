#Requires -Version 5.1
<#
.SYNOPSIS
    Bump version, build the installer, push a tag, and publish a GitHub release.

.DESCRIPTION
    Normal flow (no -SkipBuild):
      1. Fetches tags from origin to find the current released version
      2. Prompts for patch / minor / major bump (or pass a flag)
      3. Updates __version__ in budget_tracker/__init__.py
      4. Runs build.ps1
      5. Commits the version bump, tags it, and pushes commit + tag
      6. Creates a GitHub release via the REST API and uploads the installer

    -SkipBuild flow:
      Finds the newest BudgetTracker-*-Setup.exe already in dist\,
      reads its version from the filename, then tags, pushes, and publishes
      without touching __init__.py or rebuilding.

    GitHub release creation uses the REST API directly (only needs the
    "repo" scope -- no "workflow" scope required). The token is read from
    "gh auth token".

.PARAMETER Patch / Minor / Major
    Which version component to bump. Ignored when -SkipBuild is used.
    If none supplied in normal mode, prompts interactively.

.PARAMETER SkipBuild
    Skip the build. Uses whatever exe is already in dist\.

.PARAMETER Draft
    Create the GitHub release as a draft.

.PARAMETER Prerelease
    Mark the GitHub release as a pre-release.

.EXAMPLE
    .\scripts\release.ps1            # interactive bump + build + publish
    .\scripts\release.ps1 -Minor     # non-interactive minor bump
    .\scripts\release.ps1 -SkipBuild # publish the already-built installer
    .\scripts\release.ps1 -SkipBuild -Draft  # publish as draft for review
#>
param(
    [switch]$Patch,
    [switch]$Minor,
    [switch]$Major,
    [switch]$SkipBuild,
    [switch]$Draft,
    [switch]$Prerelease
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root     = Split-Path -Parent $PSScriptRoot
$InitFile = Join-Path $Root "budget_tracker\__init__.py"

# ---------------------------------------------------------------------------
# Fetch tags so we have an up-to-date picture of what has been released
# ---------------------------------------------------------------------------
Write-Host "Fetching tags from origin..." -ForegroundColor Cyan
git fetch --tags --quiet

# ---------------------------------------------------------------------------
# Resolve GitHub repo slug from the remote URL
#   Handles: https://github.com/owner/repo.git
#            git@github.com:owner/repo.git
#            git@github-personal:owner/repo.git  (SSH alias)
# ---------------------------------------------------------------------------
$RemoteUrl = git remote get-url origin 2>&1
if ($RemoteUrl -match '[:/]([^/:]+/[^/]+?)(?:\.git)?$') {
    $RepoSlug = $Matches[1]
} else {
    Write-Error "Cannot parse owner/repo from remote URL: $RemoteUrl"
    exit 1
}

# ===========================================================================
# PATH A: -SkipBuild
#   Find the newest installer in dist\, derive version from its filename.
# ===========================================================================
if ($SkipBuild) {
    $exes = Get-ChildItem (Join-Path $Root "dist") "BudgetTracker-*-Setup.exe" -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending
    if (-not $exes) {
        Write-Error "No BudgetTracker-*-Setup.exe found in dist\. Run build.ps1 first."
        exit 1
    }
    $SetupExe = $exes[0].FullName
    if ($SetupExe -match 'BudgetTracker-(\d+\.\d+\.\d+)-Setup\.exe') {
        $NewVersion = $Matches[1]
    } else {
        Write-Error "Cannot parse version from filename: $(Split-Path -Leaf $SetupExe)"
        exit 1
    }
    $NewTag = "v$NewVersion"
    $SizeMB = [math]::Round($exes[0].Length / 1MB, 1)
    Write-Host "Found:  $(Split-Path -Leaf $SetupExe)  ($SizeMB MB)" -ForegroundColor Green
    Write-Host "Tag:    $NewTag" -ForegroundColor Green
}
# ===========================================================================
# PATH B: Normal flow -- bump version, build, commit
# ===========================================================================
else {
    # ---- Find the latest released version tag ----
    $LatestTag = git tag --sort=-v:refname 2>&1 |
                 Where-Object { $_ -match '^v\d+\.\d+\.\d+$' } |
                 Select-Object -First 1

    if ($LatestTag) {
        $CurrentVersion = $LatestTag.TrimStart('v')
        Write-Host "Latest tag: $LatestTag" -ForegroundColor White
    } else {
        $vline = Get-Content $InitFile |
                 Where-Object { $_ -match '__version__' } |
                 Select-Object -First 1
        if ($vline -match '"([^"]+)"' -or $vline -match "'([^']+)'") {
            $CurrentVersion = $Matches[1]
        } else {
            $CurrentVersion = "0.0.0"
        }
        Write-Host "No version tags found. Using $CurrentVersion as baseline." -ForegroundColor Yellow
    }

    $parts = $CurrentVersion -split '\.'
    $Maj = [int]$parts[0]; $Min = [int]$parts[1]; $Pat = [int]$parts[2]

    # ---- Prompt if no bump flag given ----
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
}

# ---------------------------------------------------------------------------
# Guards (both paths)
# ---------------------------------------------------------------------------
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
# Normal path only: update __version__ and build
# ---------------------------------------------------------------------------
if (-not $SkipBuild) {
    $initContent = Get-Content $InitFile -Raw
    $initContent = $initContent -replace `
        '__version__\s*=\s*["''][^"'']+["'']', `
        "__version__ = `"$NewVersion`""
    [System.IO.File]::WriteAllText($InitFile, $initContent, (New-Object System.Text.UTF8Encoding $false))
    Write-Host "Updated __init__.py -> $NewVersion" -ForegroundColor Green

    Write-Host "`nRunning build.ps1..." -ForegroundColor Cyan
    & "$PSScriptRoot\build.ps1"
    if ($LASTEXITCODE -ne 0) {
        git checkout -- $InitFile
        Write-Error "build.ps1 failed. Reverted __init__.py."
        exit 1
    }

    $SetupExe = Join-Path $Root "dist\BudgetTracker-$NewVersion-Setup.exe"
    if (-not (Test-Path $SetupExe)) {
        git checkout -- $InitFile
        Write-Error "Setup exe not found after build: $SetupExe`nReverted __init__.py."
        exit 1
    }
    $SizeMB = [math]::Round((Get-Item $SetupExe).Length / 1MB, 1)
    Write-Host "Asset:  $(Split-Path -Leaf $SetupExe)  ($SizeMB MB)" -ForegroundColor Green

    Write-Host "`nCommitting version bump..." -ForegroundColor Cyan
    git add (Join-Path "budget_tracker" "__init__.py")
    git commit -m "chore: bump version to $NewVersion"
}

# ---------------------------------------------------------------------------
# Tag and push (both paths)
# ---------------------------------------------------------------------------
git tag -a $NewTag -m "Release $NewVersion"
Write-Host "Tagged $NewTag" -ForegroundColor Green

Write-Host "`nPushing..." -ForegroundColor Cyan
git push origin HEAD
if ($LASTEXITCODE -ne 0) { Write-Error "git push (commit) failed."; exit 1 }

git push origin $NewTag
if ($LASTEXITCODE -ne 0) { Write-Error "git push (tag) failed."; exit 1 }

# ---------------------------------------------------------------------------
# GitHub release via REST API (needs only "repo" scope, not "workflow")
# ---------------------------------------------------------------------------
Write-Host "`nCreating GitHub release..." -ForegroundColor Cyan

# Read stored token from gh -- no scope issues, just a local keyring read
$GhToken = gh auth token 2>&1
if ($LASTEXITCODE -ne 0 -or -not $GhToken) {
    Write-Warning "Could not read gh token -- skipping GitHub release creation."
    Write-Warning "Run 'gh auth login' then re-run with -SkipBuild to publish."
    exit 0
}

$ApiBase = "https://api.github.com"
$Headers = @{
    Authorization        = "Bearer $GhToken"
    Accept               = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

# Create the release
$ReleasePayload = @{
    tag_name               = $NewTag
    name                   = "Budget Tracker $NewVersion"
    draft                  = $Draft.IsPresent
    prerelease             = $Prerelease.IsPresent
    generate_release_notes = $true
} | ConvertTo-Json

$Release = Invoke-RestMethod `
    -Uri "$ApiBase/repos/$RepoSlug/releases" `
    -Method POST `
    -Headers $Headers `
    -Body $ReleasePayload `
    -ContentType "application/json"

# Upload the installer exe as a release asset
$AssetName    = [System.IO.Path]::GetFileName($SetupExe)
$UploadBase   = $Release.upload_url -replace '\{[^}]+\}', ''
$AssetBytes   = [System.IO.File]::ReadAllBytes($SetupExe)

Write-Host "Uploading $AssetName..." -ForegroundColor Cyan
$null = Invoke-RestMethod `
    -Uri "${UploadBase}?name=$AssetName" `
    -Method POST `
    -Headers $Headers `
    -Body $AssetBytes `
    -ContentType "application/octet-stream"

Write-Host "`nDone." -ForegroundColor Green
if ($Draft) {
    Write-Host "Draft release (finish on GitHub): $($Release.html_url)" -ForegroundColor Yellow
} else {
    Write-Host "Published: $($Release.html_url)" -ForegroundColor Cyan
}