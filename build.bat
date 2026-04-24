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
