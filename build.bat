@echo off
setlocal

echo ============================================
echo  Building Container Tracker
echo ============================================

echo [1/3] Installing dependencies...
pip install requests openpyxl customtkinter pillow pyinstaller keyring packaging --quiet
if %errorlevel% neq 0 ( echo ERROR: pip install failed. & exit /b 1 )

echo [2/3] Compiling ContainerTracker.exe...
pyinstaller ^
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
