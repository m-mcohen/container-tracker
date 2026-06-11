@echo off
setlocal

echo ============================================
echo  Building Container Tracker
echo ============================================

REM Build target is Python 3.12. pywebview's Windows backend (pythonnet) has
REM no stable wheels for 3.13+, and PyInstaller hooks for pywebview are
REM tested against 3.12. Use the py launcher so this runs under the right
REM interpreter regardless of what's first on PATH.
REM Python version must match requires-python in pyproject.toml.
py -3.12 --version >nul 2>&1
if %errorlevel% neq 0 ( echo ERROR: Python 3.12 not found. Install via: winget install Python.Python.3.12 & exit /b 1 )

echo [1/4] Installing dependencies...
py -3.12 -m pip install -r requirements-build.txt --quiet
if %errorlevel% neq 0 ( echo ERROR: pip install failed. & exit /b 1 )

echo [2/4] Compiling ContainerTracker.exe...
py -3.12 -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "ContainerTracker" ^
    --icon app.ico ^
    --paths . ^
    --add-data "app.ico;." ^
    --add-data "container_tracker/web;container_tracker/web" ^
    --collect-all webview ^
    --collect-all keyring ^
    --distpath "dist" ^
    container_tracker/__main__.py

if %errorlevel% neq 0 ( echo ERROR: PyInstaller build failed. & exit /b 1 )

echo [3/4] Generating version.iss from constants.py...
REM installer.iss #includes version.iss so the installer version always
REM matches __version__ (single source of truth). chr(34) avoids nested
REM double-quote escaping inside the cmd-quoted python -c string.
py -3.12 -c "from container_tracker.core.constants import __version__ as v; open('version.iss','w').write('#define AppVersion ' + chr(34) + v + chr(34) + chr(10))"
if %errorlevel% neq 0 ( echo ERROR: version.iss generation failed. & exit /b 1 )

echo [4/4] Done.
echo.
echo ============================================
echo  BUILD COMPLETE
echo ============================================
echo   Output: dist\ContainerTracker.exe
echo.
exit /b 0
