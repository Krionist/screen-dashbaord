@echo off
REM Starts the PC Bridge fully hidden (no console window). Logs go to pc-bridge.log.
REM For a visible console (debugging) use start-bridge-debug.bat.
cd /d "%~dp0"
start "" wscript.exe "%~dp0start-bridge-hidden.vbs"
exit
