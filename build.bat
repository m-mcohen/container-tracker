@echo off
REM ============================================================
REM  Build Container Tracker into a standalone Windows .exe
REM ============================================================

echo ============================================
echo  Building Container ETA Tracker .exe
echo ============================================
echo.

echo [1/3] Installing dependencies...
pip install requests openpyxl customtkinter pillow pyinstaller --quiet
if %errorlevel% neq 0 (
    echo ERROR: Failed to install packages.
    pause
    exit /b 1
)

echo [2/3] Compiling application...
pyinstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "ContainerTracker" ^
    --icon "crate.ico" ^
    --collect-all customtkinter ^
    container_tracker_gui.py

if %errorlevel% neq 0 (
    echo ERROR: Build failed.
    pause
    exit /b 1
)

echo [3/3] Preparing delivery package...
if not exist "delivery" mkdir delivery
copy dist\ContainerTracker.exe delivery\
copy README_CLIENT.md delivery\

echo.
echo ============================================
echo  BUILD COMPLETE!
echo ============================================
echo.
echo  Delivery package is in the "delivery" folder:
echo    delivery\ContainerTracker.exe
echo    delivery\README_CLIENT.md
echo.
pause
