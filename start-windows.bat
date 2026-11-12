@echo off
REM ==========================================================================
REM  DocExtract Pro - start without Docker (Windows)
REM  Double-click this file, or run:  start-windows.bat
REM  First run installs everything (10-30 minutes with OCR). Later runs start
REM  in seconds. Run "start-windows.bat rebuild" after updating the code.
REM ==========================================================================
setlocal EnableExtensions
cd /d "%~dp0"
title DocExtract Pro
if not defined VENV_DIR set "VENV_DIR=.venv"
set "PY=%VENV_DIR%\Scripts\python.exe"

REM ---- 1. Settings file ----------------------------------------------------
if not exist ".env" (
    copy /y ".env.example" ".env" >nul
    echo.
    echo  A settings file ".env" was created. Fill in at least:
    echo    SECRET_KEY, APP_ADMIN_USERNAME, APP_ADMIN_PASSWORD,
    echo    WHATSAPP_APP_SECRET, WHATSAPP_VERIFY_TOKEN and your AI key.
    echo  Then save it and run this file again.
    echo.
    start "" notepad ".env"
    pause
    exit /b 1
)

REM ---- 2. Python environment ----------------------------------------------
if not exist "%PY%" (
    set "PYCMD="
    for %%V in (3.11 3.12 3.10) do (
        if not defined PYCMD py -%%V -c "import sys" >nul 2>&1 && set "PYCMD=py -%%V"
    )
    if not defined PYCMD (
        echo.
        echo  Python 3.11 was not found. Install it from
        echo    https://www.python.org/downloads/release/python-3119/
        echo  ^(tick "Add python.exe to PATH"^), then run this file again.
        echo.
        pause
        exit /b 1
    )
    echo Creating the Python environment...
    call %%PYCMD%% -m venv "%VENV_DIR%" || goto :fail
)

echo Checking Python packages...
"%PY%" -m pip install --disable-pip-version-check -q --upgrade pip || goto :fail
"%PY%" -m pip install --disable-pip-version-check -q -r backend\requirements.txt || goto :fail
findstr /R /I /C:"^INSTALL_OCR=true" .env >nul 2>&1
if not errorlevel 1 (
    echo Checking OCR packages ^(large download on the first run^)...
    "%PY%" -m pip install --disable-pip-version-check -q -r backend\requirements-ocr.txt || goto :fail
)

REM ---- 3. Web app -------------------------------------------------------
if /i "%~1"=="rebuild" goto :build
if exist "frontend\dist\index.html" goto :run
:build
where npm >nul 2>&1
if errorlevel 1 (
    echo.
    echo  The web app is not built yet and Node.js was not found.
    echo  Install Node.js 20 LTS from https://nodejs.org and run this file again.
    echo.
    pause
    exit /b 1
)
echo Building the web app...
pushd frontend
call npm ci --no-audit --no-fund || (popd & goto :fail)
call npm run build || (popd & goto :fail)
popd

REM ---- 4. Start ----------------------------------------------------------
:run
set "SERVE_FRONTEND=true"
"%PY%" -m backend.serve
echo.
echo  The server stopped. Read the messages above for the reason.
pause
exit /b 0

:fail
echo.
echo  Setup failed. Read the error above, fix it and run this file again.
pause
exit /b 1
