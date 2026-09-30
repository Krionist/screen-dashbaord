@echo off
REM Get Monitor Information Script
REM This script displays the exact coordinates and sizes of all monitors

cd /d "%~dp0"

echo ========================================
echo Monitor Information Tool
echo ========================================
echo.

REM Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Check if pywin32 is installed
python -c "import win32api" 2>nul
if errorlevel 1 (
    echo pywin32 not found, installing...
    pip install pywin32
)

echo.
echo Getting monitor information...
echo.

python get_monitors.py

echo.
pause
