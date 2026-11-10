@echo off
setlocal enabledelayedexpansion

REM ==============================================================================
REM DockPilot - Service Shutdown Script
REM Safely stops the FastAPI backend and Docker monitoring containers
REM WITHOUT deleting persistent volumes, historical metrics, or configurations.
REM ==============================================================================

echo ==============================================================================
echo                        Stopping DockPilot Services
echo ==============================================================================
echo.

cd /d "%~dp0"

REM 1. Stop FastAPI Backend Process
echo [1/2] Stopping DockPilot FastAPI backend on port 8001...
set KILLED_ANY=0
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr :8001 ^| findstr LISTENING') do (
    echo   Terminating backend process PID: %%a...
    taskkill /F /PID %%a >nul 2>&1
    if !errorlevel! equ 0 (
        echo   [PASS] Stopped backend process with PID %%a.
        set KILLED_ANY=1
    )
)
if !KILLED_ANY! equ 0 (
    echo   [INFO] No active backend process found listening on port 8001.
)
echo.

REM 2. Stop Docker Monitoring Containers (Without Volume Removal)
echo [2/2] Stopping Docker monitoring containers...
docker info >nul 2>&1
if %errorlevel% equ 0 (
    docker compose -f monitoring-compose.yaml stop
    if !errorlevel! equ 0 (
        echo   [PASS] Docker monitoring services stopped successfully.
    ) else (
        echo   [WARN] Encountered issues stopping containers via Docker Compose.
    )
) else (
    echo   [INFO] Docker daemon is not running; skipping container stop.
)
echo.

echo ==============================================================================
echo                     DockPilot Services Safely Stopped
echo ==============================================================================
echo.
echo   All persistent data has been preserved:
echo     - Prometheus TSDB Volume:   dockpilot_prometheus_data   (Intact)
echo     - Grafana Dashboard Volume: dockpilot_grafana_data      (Intact)
echo     - Alertmanager Volume:      dockpilot_alertmanager_data (Intact)
echo     - DockPilot SQLite History: data\dockpilot_history.db   (Intact)
echo.
echo   To start DockPilot again:  start.bat
echo   To run health checks:      check-monitoring.bat
echo ==============================================================================
exit /b 0
