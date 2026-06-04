@echo off
chcp 65001 >nul 2>&1
setlocal EnableDelayedExpansion

set "ROOT=%~dp0"
cd /d "%ROOT%"

echo.
echo ========================================
echo   ???? + Token-Mail Integrated System
echo ========================================
echo.

for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":18080 " ^| findstr "LISTENING"') do (
    echo [INFO] Port 18080 is occupied by PID %%a, terminating...
    taskkill /PID %%a /F >nul 2>&1
    if not errorlevel 1 (
        echo [OK] Old process killed.
    ) else (
        echo [WARN] Could not kill PID %%a.
    )
    timeout /t 1 /nobreak >nul
)

set "PY="
where py >nul 2>nul
if not errorlevel 1 (
    set "PY=py -3"
    goto :found_py
)
where python >nul 2>nul
if not errorlevel 1 (
    set "PY=python"
    goto :found_py
)
echo [ERROR] Python not found
pause
exit /b 1

:found_py
echo [OK] Python: %PY%

echo [1/2] Checking dependencies...
%PY% -c "import fastapi, uvicorn, sqlalchemy, httpx, pydantic" >nul 2>nul
if errorlevel 1 (
    echo       Installing web deps...
    %PY% -m pip install fastapi uvicorn sqlalchemy httpx pydantic python-multipart --quiet --disable-pip-version-check
)
%PY% -c "import selenium, faker" >nul 2>nul
if errorlevel 1 (
    echo       Installing ???? deps...
    %PY% -m pip install selenium undetected-chromedriver faker toml ddddocr PySocks requests fake_useragent --quiet --disable-pip-version-check
)
echo [OK] Dependencies ready

echo [2/2] Starting FastAPI integrated server...
echo.
echo ========================================
echo   http://localhost:18080
echo   Press Ctrl+C to stop
echo ========================================
echo.

set "PYTHONPATH=%ROOT%????;%ROOT%;%PYTHONPATH%"
%PY% "%ROOT%integrated_server.py"
if not "%ERRORLEVEL%"=="0" (
    echo.
    echo [ERROR] Exit code: %ERRORLEVEL%
    pause
)

