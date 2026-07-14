@echo off
setlocal
title Airpay Reconciliation - Streamlit
cd /d "%~dp0"

REM ============================================================================
REM  One-click launcher for the Airpay Reconciliation Streamlit app (app_1.py).
REM  Double-click this file to start the UI in your browser.
REM ============================================================================

REM --- Locate Python ---
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY ( where python3 >nul 2>nul && set "PY=python3" )
if not defined PY (
  echo [ERROR] Python 3 not found on PATH.
  echo Install Python 3 from https://python.org ^(tick "Add to PATH"^) and run this again.
  pause
  exit /b 1
)
echo Using Python: %PY%

REM --- First-run dependency install (skipped on later launches) ---
if not exist ".deps-installed" (
  echo Installing dependencies ^(first run only^)...
  %PY% -m pip install -r requirements.txt || (
    echo [ERROR] Dependency install failed.
    pause
    exit /b 1
  )
  echo ok > .deps-installed
)

echo.
echo Starting Airpay Reconciliation...
echo If your browser doesn't open automatically, go to:
echo     http://localhost:8501
echo.
echo Press Ctrl+C in this window to stop the server.
echo.

start "" http://localhost:8501
%PY% -m streamlit run app_1.py --server.headless true

pause
endlocal
