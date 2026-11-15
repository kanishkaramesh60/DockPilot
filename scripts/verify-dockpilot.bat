@echo off
setlocal enabledelayedexpansion

REM ==============================================================================
REM DockPilot - Comprehensive Verification and Health Check Script
REM Platform: Windows 10 / 11 (CMD compatible)
REM Verifies all 6 services, Prometheus targets, alert rules, and APIs.
REM ==============================================================================

echo ==============================================================================
echo                DockPilot Comprehensive System Verification
echo ==============================================================================
echo.

cd /d "%~dp0\.."
set "PROJECT_ROOT=%cd%"

set "PYTHON_EXE="
if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
) else if exist "%PROJECT_ROOT%\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%PROJECT_ROOT%\venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

REM 1. Docker Daemon Check
echo [1/3] Checking Docker daemon status...
docker info >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Docker daemon is running and accessible.
) else (
    echo   [FAIL] Docker daemon is not accessible.
    echo          Please start Docker Desktop and try again.
    exit /b 1
)
echo.

REM 2. Persistent Storage Volumes Verification
echo [2/3] Checking persistent storage volumes...
set VOLUMES_CHECK=1
for %%v in (dockpilot_dockpilot_prometheus_data dockpilot_dockpilot_grafana_data dockpilot_dockpilot_alertmanager_data) do (
    docker volume inspect %%v >nul 2>&1
    if !errorlevel! neq 0 (
        echo   [FAIL] Persistent volume missing: %%v
        set VOLUMES_CHECK=0
    ) else (
        echo   [PASS] Persistent volume intact: %%v
    )
)
if !VOLUMES_CHECK! equ 0 (
    echo   [FAIL] One or more persistent volumes are missing.
    exit /b 1
)
echo.

REM 3. Service & API Probing
echo [3/3] Probing services, Prometheus scrape targets, and alert evaluation...
"%PYTHON_EXE%" "%PROJECT_ROOT%\scripts\verify_services.py"
exit /b %errorlevel%
