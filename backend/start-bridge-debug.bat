@echo off
REM PC Bridge Launcher Script
REM This script starts the PC monitoring bridge


cd /d "%~dp0"

echo ========================================
echo PC Bridge - Windows PC Monitoring API
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found!
    echo Please create it first: python -m venv venv
  6  echo Then install dependencies: pip install -r requirements.txt
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if requirements are installed
python -c "import flask" 2>nul
if errorlevel 1 (
    echo Dependencies not installed!
    echo Installing requirements...
    pip install -r requirements.txt
)

echo.
echo Starting PC Bridge...
echo Dashboard will be available at: http://localhost:9101/
echo Opening Chrome browser on monitor 3 in kiosk mode...
echo Press Ctrl+C to stop
echo.

REM Start the bridge with kiosk mode
REM Use --monitor 1, 2, or 3 to choose which monitor (default: 3)
python pc-bridge.py --kiosk

pause