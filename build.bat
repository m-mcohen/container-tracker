@echo off
setlocal

echo ============================================
echo  Building Container Tracker
echo ============================================

REM Build target is Python 3.12. pywebview's Windows backend (pythonnet) has
REM no stable wheels for 3.13+, and PyInstaller hooks for pywebview are
REM tested against 3.12. Use the py launcher so this runs under the right
REM interpreter regardless of what's first on PATH.
py -3.12 --version >nul 2>&1
if %errorlevel% neq 0 ( echo ERROR: Python 3.12 not found. Install via: winget install Python.Python.3.12 & exit /b 1 )

echo [1/3] Installing dependencies...
py -3.12 -m pip install requests openpyxl customtkinter pillow pyinstaller keyring packaging --quiet
if %errorlevel% neq 0 ( echo ERROR: pip install failed. & exit /b 1 )

echo [2/3] Compiling ContainerTracker.exe...
py -3.12 -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "ContainerTracker" ^
    --icon app.ico ^
    --add-data "app.ico;." ^
    --collect-all customtkinter ^
    --collect-all keyring ^
    --distpath "dist" ^
    container_tracker_gui.py

if %errorlevel% neq 0 ( echo ERROR: PyInstaller build failed. & exit /b 1 )

echo [3/3] Done.
echo.
echo ============================================
echo  BUILD COMPLETE
echo ============================================
echo   Output: dist\ContainerTracker.exe
echo.
exit /b 0
