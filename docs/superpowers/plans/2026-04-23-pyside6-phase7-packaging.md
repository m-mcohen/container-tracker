# Phase 7 — Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans.

**Goal:** Produce `dist/installer/ContainerTracker_Setup_v1.1.0.exe` ready for distribution. Verify it installs cleanly over the existing v1.0.0 on this machine without losing config or tracking data. **STOP before uploading to GitHub Releases** — user handles publication.

**Architecture:** PyInstaller consumes the new package entry point `container_tracker/__main__.py` with `--collect-all PySide6 --collect-all keyring`. Inno Setup wraps the resulting `.exe` in a signed-with-user-privileges installer that keeps the v1.0.0 `AppId` GUID — that's what Windows uses to recognize the upgrade and preserve the install path.

**Tech Stack:** PyInstaller ≥ 6, Inno Setup 6 (iscc.exe at `C:\Program Files (x86)\Inno Setup 6\ISCC.exe` or `C:\Program Files\Inno Setup 6\ISCC.exe`).

**Spec:** [2026-04-23-pyside6-migration-design.md §7](../specs/2026-04-23-pyside6-migration-design.md)

---

## Single checkpoint. Eight tasks.

- **Task 1:** Rewrite `ContainerTracker.spec` — new entry point `container_tracker/__main__.py`; `collect_all('PySide6')` + `collect_all('keyring')`; drop CustomTkinter.
- **Task 2:** Rewrite `build.bat` — new entry point, new deps (PySide6), drop CustomTkinter.
- **Task 3:** Update `installer.iss` — `AppVersion 1.1.0`, add `ATTRIBUTIONS.md` to `[Files]`.
- **Task 4:** Build the `.exe` (`pyinstaller ContainerTracker.spec --noconfirm`); verify size 40–60 MB, app.ico bundled.
- **Task 5:** Launch the standalone `.exe` directly to verify it works outside the installer.
- **Task 6:** Compile the installer via `iscc.exe installer.iss`; verify the output path.
- **Task 7:** Backup user data, run the installer silently, verify app launches from installed location, verify config + tracking data intact.
- **Task 8:** Commit build artifacts summary (NOT the installer .exe itself — too large; it goes in the GitHub Release).

**STOP HERE.** Do NOT attempt to upload to GitHub Releases. That's a user-approved step.

**Standing conventions:** `mypy --strict container_tracker` clean (no logic changes in Phase 7). Commits per task for source-file changes. No `--no-verify`.

---

## Task 1: Rewrite `ContainerTracker.spec`

**Files:**
- Modify: `ContainerTracker.spec`

- [ ] **Step 1: Replace the file with:**

```python
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('app.ico', '.')]
binaries = []
hiddenimports = []

# PySide6: platforms, imageformats, styles — required or the app crashes at launch
# on machines without Qt installed system-wide.
tmp_ret = collect_all('PySide6')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# keyring: Windows Credential Manager backend is discovered dynamically; PyInstaller
# otherwise misses keyring.backends.Windows.
tmp_ret = collect_all('keyring')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['container_tracker/__main__.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ContainerTracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['app.ico'],
)
```

- [ ] **Step 2: Commit**

```bash
git add ContainerTracker.spec
git commit -m "build: rewrite PyInstaller spec for PySide6 entry point (drop CustomTkinter)"
```

---

## Task 2: Rewrite `build.bat`

**Files:**
- Modify: `build.bat`

- [ ] **Step 1: Replace the file with:**

```bat
@echo off
setlocal

echo ============================================
echo  Building Container Tracker v1.1.0
echo ============================================

echo [1/3] Installing dependencies...
pip install PySide6 requests openpyxl keyring packaging pyinstaller --quiet
if %errorlevel% neq 0 ( echo ERROR: pip install failed. & exit /b 1 )

echo [2/3] Compiling ContainerTracker.exe...
pyinstaller ^
    --noconfirm ^
    --clean ^
    ContainerTracker.spec

if %errorlevel% neq 0 ( echo ERROR: PyInstaller build failed. & exit /b 1 )

echo [3/3] Done.
echo.
echo ============================================
echo  BUILD COMPLETE
echo ============================================
echo   Output: dist\ContainerTracker.exe
echo.
exit /b 0
```

- [ ] **Step 2: Commit**

```bash
git add build.bat
git commit -m "build: update build.bat for PySide6 deps + spec-driven PyInstaller invocation"
```

---

## Task 3: Update `installer.iss`

**Files:**
- Modify: `installer.iss`

- [ ] **Step 1: Change the `AppVersion` define**

```
#define AppVersion "1.1.0"
```

(Was `1.0.0`.)

- [ ] **Step 2: Add `ATTRIBUTIONS.md` to `[Files]`**

Find the existing `[Files]` section and add a line:

```
Source: "ATTRIBUTIONS.md"; DestDir: "{app}"; Flags: ignoreversion
```

Keep all other entries (including `README_CLIENT.md` with `isreadme`).

- [ ] **Step 3: Confirm `AppId` is unchanged**

`AppId={{867023ab-b5bc-48d0-8093-961789d93187}}` — this GUID must NOT change. It's what Windows uses to detect upgrades. Changing it would make the v1.1.0 installer install alongside v1.0.0 as a second product.

- [ ] **Step 4: Commit**

```bash
git add installer.iss
git commit -m "installer: bump AppVersion to 1.1.0; bundle ATTRIBUTIONS.md"
```

---

## Task 4: Build the `.exe`

**Files:** none modified.

- [ ] **Step 1: Clean previous build artifacts**

```powershell
Remove-Item -Recurse -Force "build","dist" -ErrorAction SilentlyContinue
```

- [ ] **Step 2: Run PyInstaller via the spec file**

```powershell
pyinstaller --noconfirm --clean ContainerTracker.spec
```

Expected: PyInstaller output ends with `Building EXE from EXE-00.toc completed successfully.` or similar. Exit code 0.

- [ ] **Step 3: Verify the `.exe` exists and its size is 40–60 MB**

```powershell
$exe = "dist\ContainerTracker.exe"
if (-not (Test-Path $exe)) { Write-Error "FAILURE: $exe not produced"; exit 1 }
$size_mb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Output "Size: $size_mb MB"
if ($size_mb -lt 30 -or $size_mb -gt 80) { Write-Warning "Unexpected size (expected 40-60 MB)" }
```

Expected: size between 30 and 80 MB. v1.0.0 was 33 MB on CustomTkinter; v1.1.0 with PySide6 is typically 50–60 MB.

- [ ] **Step 4: Verify `app.ico` was bundled**

Use a PowerShell one-liner or a quick Python check. Simplest: the `.exe` has an embedded icon already via `--icon`; the `--add-data "app.ico;."` is for runtime access. You can spot-check by looking inside the spec file (already verified) and by launching the app in Task 5 — the window icon comes from `app.ico` bundled via resource.

- [ ] **Step 5: No commit** — artifacts in `dist/` are gitignored.

---

## Task 5: Launch the standalone `.exe`

**Files:** none modified.

- [ ] **Step 1: Use PowerShell retry-loop pattern**

```powershell
$ErrorActionPreference = "Stop"
$exe = "C:/Users/emine/OneDrive/Documents/Claude/container_tracking_build/dist/ContainerTracker.exe"
$proc = Start-Process -FilePath $exe -PassThru
$deadline = (Get-Date).AddSeconds(15)  # bundled exe takes longer to start
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 500
    $proc.Refresh()
    if ($proc.MainWindowHandle -ne 0 -and -not [string]::IsNullOrEmpty($proc.MainWindowTitle)) { break }
}
if ($proc.MainWindowHandle -eq 0 -or [string]::IsNullOrEmpty($proc.MainWindowTitle)) {
    Write-Output "FAILURE: standalone .exe window never registered"
    Stop-Process -Id $proc.Id -Force
    exit 1
}
Write-Output "OK: PID=$($proc.Id) Title='$($proc.MainWindowTitle)' Handle=$($proc.MainWindowHandle)"
$proc.CloseMainWindow() | Out-Null
$proc.WaitForExit(10000) | Out-Null
Write-Output "Exit=$($proc.ExitCode)"
```

Expected: handle non-zero, title contains `Container Tracker v1.1.0`, clean exit 0. If the launch hangs past 15s, the bundled PySide6 plugins aren't being found. Check `build/ContainerTracker/warn-ContainerTracker.txt` for hints.

- [ ] **Step 2: No commit.**

---

## Task 6: Compile the installer

**Files:** none modified.

- [ ] **Step 1: Locate ISCC.exe**

```powershell
$iscc = $null
foreach ($p in @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 5\ISCC.exe"
)) {
    if (Test-Path $p) { $iscc = $p; break }
}
if (-not $iscc) {
    Write-Output "FAILURE: ISCC.exe not found; install Inno Setup 6 from https://jrsoftware.org/isdl.php"
    exit 1
}
Write-Output "Using $iscc"
```

- [ ] **Step 2: Compile**

```powershell
& $iscc "installer.iss"
```

Expected: output ends with "Successful compile" or "1 file(s) compiled". Exit code 0.

- [ ] **Step 3: Verify the installer exists**

```powershell
$installer = "dist\installer\ContainerTracker_Setup_v1.1.0.exe"
if (-not (Test-Path $installer)) {
    Write-Output "FAILURE: $installer not produced"
    exit 1
}
$size_mb = [math]::Round((Get-Item $installer).Length / 1MB, 1)
Write-Output "Installer size: $size_mb MB (path: $installer)"
```

Expected: installer size in the 20–35 MB range (Inno Setup's LZMA2 compresses the PyInstaller bundle substantially).

- [ ] **Step 4: No commit.**

---

## Task 7: Install over v1.0.0 and smoke-test

**Files:** none modified.

- [ ] **Step 1: Backup user data (paranoia)**

```powershell
$appdata_dir = "$env:APPDATA\ContainerTracker"
$backup_dir = "$env:APPDATA\ContainerTracker.phase7-backup"
if (Test-Path $appdata_dir) {
    if (Test-Path $backup_dir) { Remove-Item -Recurse -Force $backup_dir }
    Copy-Item -Recurse $appdata_dir $backup_dir
    Write-Output "Backed up user data to $backup_dir"
}
```

- [ ] **Step 2: Capture pre-install state**

```powershell
$config_before = Get-Content "$appdata_dir\config.json" -Raw -ErrorAction SilentlyContinue
$tracking_before = Get-Content "$appdata_dir\tracking_data.json" -Raw -ErrorAction SilentlyContinue
Write-Output "Pre-install config.json length: $($config_before.Length)"
Write-Output "Pre-install tracking_data.json length: $($tracking_before.Length)"
```

- [ ] **Step 3: Close any running v1.0.0 instance**

```powershell
Get-Process ContainerTracker -ErrorAction SilentlyContinue | ForEach-Object {
    $_.CloseMainWindow() | Out-Null
    $_.WaitForExit(5000) | Out-Null
    if (-not $_.HasExited) { Stop-Process -Id $_.Id -Force }
}
```

- [ ] **Step 4: Run the installer silently**

```powershell
$installer = "dist\installer\ContainerTracker_Setup_v1.1.0.exe"
$proc = Start-Process -FilePath $installer -ArgumentList "/SILENT","/NORESTART","/SUPPRESSMSGBOXES" -PassThru -Wait
Write-Output "Installer exit code: $($proc.ExitCode)"
if ($proc.ExitCode -ne 0) {
    Write-Output "FAILURE: installer exited with code $($proc.ExitCode)"
    exit 1
}
```

- [ ] **Step 5: Verify the installed exe exists in the expected location**

```powershell
$installed = "$env:LOCALAPPDATA\Programs\ContainerTracker\ContainerTracker.exe"
if (-not (Test-Path $installed)) {
    Write-Output "FAILURE: installed exe not at $installed"
    exit 1
}
$installed_size = [math]::Round((Get-Item $installed).Length / 1MB, 1)
Write-Output "Installed exe: $installed ($installed_size MB)"
```

- [ ] **Step 6: Verify user data was preserved by the installer**

```powershell
$config_after = Get-Content "$appdata_dir\config.json" -Raw -ErrorAction SilentlyContinue
$tracking_after = Get-Content "$appdata_dir\tracking_data.json" -Raw -ErrorAction SilentlyContinue

if ($config_before -ne $config_after) {
    Write-Output "FAILURE: config.json changed during install"
    Write-Output "BEFORE: $config_before"
    Write-Output "AFTER:  $config_after"
    exit 1
}
if ($tracking_before -ne $tracking_after) {
    Write-Output "FAILURE: tracking_data.json changed during install"
    exit 1
}
Write-Output "User data preserved cleanly through upgrade."
```

- [ ] **Step 7: Launch the installed app and verify version**

```powershell
$proc = Start-Process -FilePath $installed -PassThru
$deadline = (Get-Date).AddSeconds(15)
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 500
    $proc.Refresh()
    if ($proc.MainWindowHandle -ne 0 -and -not [string]::IsNullOrEmpty($proc.MainWindowTitle)) { break }
}
if ($proc.MainWindowHandle -eq 0) {
    Write-Output "FAILURE: installed app window never registered"
    Stop-Process -Id $proc.Id -Force
    exit 1
}
Write-Output "Installed app OK: Title='$($proc.MainWindowTitle)' Handle=$($proc.MainWindowHandle)"
if ($proc.MainWindowTitle -notmatch "1\.1\.0") {
    Write-Output "FAILURE: installed app title does not contain 1.1.0 — upgrade may have failed"
    $proc.CloseMainWindow() | Out-Null
    exit 1
}
$proc.CloseMainWindow() | Out-Null
$proc.WaitForExit(10000) | Out-Null
Write-Output "Installed-app exit code: $($proc.ExitCode)"
```

- [ ] **Step 8: Clean up the backup**

Only if everything above passed. Keep the backup if any step failed.

```powershell
Remove-Item -Recurse -Force $backup_dir
Write-Output "Cleanup: removed $backup_dir (install succeeded)"
```

- [ ] **Step 9: No commit.**

---

## Task 8: Commit a build-summary note so the installer build is recorded

**Files:**
- Create: `docs/superpowers/build-log-v1.1.0.md`

Record what was built, sizes, smoke-test results. This gives the user tomorrow a paper trail for what shipped.

- [ ] **Step 1: Write the log**

Template:

```markdown
# v1.1.0 Build Log — <DATE>

## Artifacts

- `dist/ContainerTracker.exe` — <SIZE> MB (PyInstaller --onefile --windowed)
- `dist/installer/ContainerTracker_Setup_v1.1.0.exe` — <SIZE> MB (Inno Setup)

## Build environment

- Python: <python --version>
- PyInstaller: <pyinstaller --version>
- Inno Setup: <ISCC path>
- OS: Windows 11 (Python 3.14.x on this machine — confirmed working)

## Smoke test results

### Standalone .exe

- Launch handle: <HANDLE>
- Window title: <TITLE>
- Exit on WM_CLOSE: <EXIT_CODE>

### Installed .exe (after silent upgrade from v1.0.0)

- Installer exit code: <CODE>
- Installed path: %LOCALAPPDATA%\Programs\ContainerTracker\ContainerTracker.exe
- Installed size: <SIZE> MB
- config.json preserved: <yes/no>
- tracking_data.json preserved: <yes/no>
- Launch title: <TITLE>
- Exit code: <EXIT_CODE>

## Ready to ship

- AppId unchanged from v1.0.0 → Windows recognizes as upgrade.
- ATTRIBUTIONS.md bundled.
- README_CLIENT.md bundled (isreadme).
- User data migration: none needed — v1.0.0 config format matches v1.1.0.

**Upload to GitHub Releases: pending user approval.**
```

Fill in the actual values from Tasks 4, 5, 6, 7 before committing.

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/build-log-v1.1.0.md
git commit -m "docs: v1.1.0 build log — installer built, smoke test passed, awaiting upload approval"
```

---

## PHASE 7 COMPLETE

**DO NOT** upload the installer to GitHub Releases. That step is user-approved only.

Return to the orchestrator with a summary of:

- Exe + installer sizes
- Standalone launch test result
- Installer install-over-v1.0.0 result
- User data preservation verification
- Version displayed by installed app
- Any deviations
- `git log --oneline -15`

---

## Self-Review

**Spec §7 coverage:**
- `--onefile --windowed --icon app.ico --add-data "app.ico;." --name ContainerTracker --collect-all PySide6 --collect-all keyring` — Task 1 encodes all of these in the .spec.
- Expected 40–60 MB exe — Task 4 Step 3 verifies.
- `installer.iss` keeps AppId, bumps AppVersion, adds ATTRIBUTIONS — Task 3.
- Output `dist\installer\ContainerTracker_Setup_v1.1.0.exe` — Task 6.
- Install over v1.0.0 as smoke test — Task 7.

**Placeholder scan:** Task 8 template has angle-bracket placeholders INTENTIONALLY so the executor fills them with real values. That's not a plan-placeholder — it's a document-template. Acceptable.

**Type consistency:** N/A — no Python code changes in Phase 7.

**Stop condition:** installer built and smoke-tested locally, but the `.exe` is NOT pushed to GitHub. User approves publication.
