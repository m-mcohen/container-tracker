# tools/release.ps1 - one-command release for Container Tracker.
#
#   .\tools\release.ps1 -Version 1.2.0              # full release
#   .\tools\release.ps1 -Version 1.2.0 -Prerelease  # marked prerelease on GitHub
#   .\tools\release.ps1 -Version 1.2.0 -BuildOnly   # bump + test + build, no git/GitHub
#
# Steps: preflight checks -> bump version (constants.py + pyproject.toml)
#   -> pytest -> build.bat (exe + version.iss) -> iscc (installer)
#   -> commit + tag + push -> gh release create with the installer attached.
#
# The single source of truth for the version is
# container_tracker/core/constants.py __version__; everything else is
# derived from it at build time (version.iss) or patched in lockstep here
# (pyproject.toml).

param(
    [Parameter(Mandatory = $true)][string]$Version,
    [switch]$Prerelease,
    [switch]$BuildOnly
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Fail($msg) { Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }

# ---- Preflight ------------------------------------------------------------
if ($Version -notmatch '^\d+\.\d+\.\d+$') { Fail "Version must be X.Y.Z (got '$Version')" }

# Native stderr is redirected inside cmd, not PowerShell: PS 5.1 turns a
# redirected native stderr line into a terminating NativeCommandError when
# $ErrorActionPreference is Stop.
cmd /c "py -3.12 --version >nul 2>&1"
if ($LASTEXITCODE -ne 0) { Fail "Python 3.12 not found. Install: winget install Python.Python.3.12" }

$isccCmd = Get-Command iscc -ErrorAction SilentlyContinue
if ($isccCmd) { $iscc = $isccCmd.Source }
else {
    $iscc = @(
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $iscc) { Fail "Inno Setup compiler (iscc) not found. Install: winget install JRSoftware.InnoSetup" }
}

if (-not $BuildOnly) {
    cmd /c "gh auth status >nul 2>&1"
    if ($LASTEXITCODE -ne 0) { Fail "gh CLI not authenticated. Run: gh auth login" }
    $dirty = git status --porcelain
    if ($dirty) { Fail "Working tree is not clean. Commit or stash first.`n$dirty" }
    # git tag --list exits 0 either way and never writes stderr.
    if (git tag --list "v$Version") { Fail "Tag v$Version already exists." }
}

# ---- Bump version (constants.py is the source of truth) --------------------
# BOM-less UTF-8 writes: PS 5.1's Set-Content -Encoding utf8 prepends a BOM,
# which pytest's TOML parser rejects ("Invalid statement at line 1, column 1").
$utf8NoBom = New-Object System.Text.UTF8Encoding $false

$constantsPath = "container_tracker\core\constants.py"
$constants = [System.IO.File]::ReadAllText((Resolve-Path $constantsPath), [System.Text.Encoding]::UTF8)
if ($constants -notmatch '__version__ = "') { Fail "__version__ not found in $constantsPath" }
$constants = $constants -replace '__version__ = "[^"]+"', "__version__ = `"$Version`""
[System.IO.File]::WriteAllText((Resolve-Path $constantsPath), $constants, $utf8NoBom)

$pyprojectPath = "pyproject.toml"
$pyproject = [System.IO.File]::ReadAllText((Resolve-Path $pyprojectPath), [System.Text.Encoding]::UTF8)
$pyproject = $pyproject -replace '(?m)^version = "[^"]+"', "version = `"$Version`""
[System.IO.File]::WriteAllText((Resolve-Path $pyprojectPath), $pyproject, $utf8NoBom)

Write-Host "[1/5] Version bumped to $Version (constants.py, pyproject.toml)" -ForegroundColor Green

# ---- Tests ------------------------------------------------------------------
# Run on the SAME interpreter the exe is built from (py -3.12), not whatever
# "python" resolves to on PATH. Deps first so a fresh 3.12 install works.
cmd /c "py -3.12 -m pip install -r requirements-build.txt pytest --quiet"
if ($LASTEXITCODE -ne 0) { Fail "pip install for the build interpreter failed" }
py -3.12 -m pytest -q
if ($LASTEXITCODE -ne 0) { Fail "Tests failed - release aborted. Version files are bumped but uncommitted; revert with: git checkout -- $constantsPath $pyprojectPath" }
Write-Host "[2/5] Tests passed" -ForegroundColor Green

# ---- Build exe + version.iss ------------------------------------------------
# Explicit .\ prefix: environments with NoDefaultCurrentDirectoryInExePath
# set won't resolve bare "build.bat" from the current directory.
cmd /c "cd /d ""$repoRoot"" && .\build.bat"
if ($LASTEXITCODE -ne 0) { Fail "build.bat failed" }
Write-Host "[3/5] dist\ContainerTracker.exe built" -ForegroundColor Green

# ---- Build installer ----------------------------------------------------------
& $iscc installer.iss
if ($LASTEXITCODE -ne 0) { Fail "iscc failed" }
$installer = "dist\installer\ContainerTracker_Setup_v$Version.exe"
if (-not (Test-Path $installer)) { Fail "Expected installer not found: $installer" }
Write-Host "[4/5] $installer built" -ForegroundColor Green

if ($BuildOnly) {
    Write-Host "[5/5] -BuildOnly: skipping commit/tag/release. Version files are modified but uncommitted." -ForegroundColor Yellow
    exit 0
}

# ---- Commit, tag, push, release ----------------------------------------------
git add $constantsPath $pyprojectPath
git commit -m "release: v$Version"
if ($LASTEXITCODE -ne 0) { Fail "git commit failed" }
git tag "v$Version"
$branch = git rev-parse --abbrev-ref HEAD
git push origin $branch
if ($LASTEXITCODE -ne 0) { Fail "git push failed" }
git push origin "v$Version"
if ($LASTEXITCODE -ne 0) { Fail "tag push failed" }

$flags = @("--title", "v$Version", "--generate-notes")
if ($Prerelease) { $flags += "--prerelease" }
gh release create "v$Version" $installer @flags
if ($LASTEXITCODE -ne 0) { Fail "gh release create failed (tag is pushed; create the release manually or re-run gh)" }

Write-Host "[5/5] Released v$Version - installer attached to the GitHub release." -ForegroundColor Green
Write-Host "Installed apps will show the update banner on next launch (requires the release to be publicly reachable)."
