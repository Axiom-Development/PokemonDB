@echo off
setlocal
rem Always run from this script's own folder, regardless of where it's launched from.
cd /d "%~dp0"

echo PokemonDB
echo ----------------------------------------
echo Starting the local server at http://127.0.0.1:8800/
echo Press Ctrl+C in this window to stop it.
echo.

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    python server.py
) else (
    py server.py
)

echo.
echo Server stopped.
pause
