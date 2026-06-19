@echo off
setlocal
title GST Recon - IMS to Books ITC Reconciliation
cd /d "%~dp0"

REM ============================================================================
REM  One-click launcher for the GST Reconciliation web frontend.
REM  Replaces the old Streamlit "run.bat": this boots the Next.js app and opens
REM  the browser at the reconciliation page. Double-click this file to start.
REM ============================================================================

REM --- Node / npm (the web frontend) ---
where npm >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js / npm not found on PATH.
  echo Install Node.js 20+ from https://nodejs.org and run this again.
  pause
  exit /b 1
)

REM --- Python (the reconciliation engine runs as a subprocess) ---
set "RECON_PYTHON="
where python >nul 2>nul && set "RECON_PYTHON=python"
if not defined RECON_PYTHON ( where python3 >nul 2>nul && set "RECON_PYTHON=python3" )
if not defined RECON_PYTHON (
  echo [ERROR] Python 3 not found on PATH.
  echo Install Python 3 from https://python.org and run this again.
  pause
  exit /b 1
)
echo Using Python interpreter: %RECON_PYTHON%

REM --- LibreOffice is needed for the final .xlsm step (warn only) ---
where soffice >nul 2>nul || where libreoffice >nul 2>nul
if errorlevel 1 (
  echo [WARN] LibreOffice not found. Report generation needs it installed.
  echo        Get it from https://www.libreoffice.org
  echo.
)

REM --- First-run setup (skipped on later launches) ---
if not exist "node_modules" (
  echo Installing Node dependencies ^(first run only^)...
  call npm install || ( echo [ERROR] npm install failed & pause & exit /b 1 )
)
if not exist "recon\.deps-installed" (
  echo Installing Python engine dependencies ^(first run only^)...
  %RECON_PYTHON% -m pip install -r recon\requirements.txt && echo ok > recon\.deps-installed
)
if not exist ".next" (
  echo Building the app ^(first run only^)...
  call npm run build || ( echo [ERROR] build failed & pause & exit /b 1 )
)

echo.
echo Starting GST Recon...
echo If your browser doesn't open automatically, go to:
echo     http://localhost:3000/recon
echo.
echo Press Ctrl+C in this window to stop the server.
echo.

start "" http://localhost:3000/recon
call npm run start

pause
endlocal
