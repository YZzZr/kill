@echo off
setlocal
cd /d "%~dp0"

REM ============================================================
REM  AutoKill Process Killer v1.0 - launcher
REM  Requires: Python 3.8+ (install from python.org, check
REM  "Add python.exe to PATH" during install)
REM ============================================================

REM 1. Ask for administrator privileges (UAC)
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs -WorkingDirectory '%~dp0'"
    exit /b
)
cd /d "%~dp0"

REM 2. Try python launcher (py), fallback to python
set "PY_EXE=py"
where py >nul 2>&1
if %errorlevel% neq 0 (
    where python >nul 2>&1
    if %errorlevel% neq 0 (
        echo [ERROR] Python not found. Please install Python 3.8+ and add it to PATH.
        pause
        exit /b 1
    )
    set "PY_EXE=python"
)

REM 3. Ensure psutil is installed
%PY_EXE% -c "import psutil" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing dependency: psutil...
    %PY_EXE% -m pip install psutil
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install psutil. Check your network and try again.
        pause
        exit /b 1
    )
)

REM 4. Run the killer script
echo.
%PY_EXE% kill_process.py
set "SCRIPT_EXIT=%errorlevel%"

if not "%SCRIPT_EXIT%"=="0" (
    echo.
    echo [ERROR] Script exited with code %SCRIPT_EXIT%
    pause
)
exit /b %SCRIPT_EXIT%
endlocal