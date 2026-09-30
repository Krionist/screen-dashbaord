@echo off
REM PC Bridge Launcher Script (No Auto-Browser)
REM This script starts the PC monitoring bridge without opening browser


cd /d "%~dp0"

echo ========================================
echo PC Bridge - Windows PC Monitoring API
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo Virtual environment not found!
    echo Please create it first: python -m venv venv
    echo Then install dependencies: pip install -r requirements.txt
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
echo Open this URL in your browser manually
echo Press Ctrl+C to stop
echo.

REM Start the bridge without kiosk mode
python pc-bridge.py

pause
