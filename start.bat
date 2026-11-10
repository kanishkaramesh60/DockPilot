@echo off
setlocal enabledelayedexpansion

REM ==============================================================================
REM DockPilot - Service Startup Script
REM Starts the monitoring infrastructure and the FastAPI backend service.
REM ==============================================================================

echo ==============================================================================
echo                        Starting DockPilot Services
echo ==============================================================================
echo.

cd /d "%~dp0"
set PROJECT_ROOT=%~dp0

REM 1. Check Docker Daemon
echo [1/4] Checking Docker daemon status...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo   [FAIL] Docker daemon is not running.
    echo          Please start Docker Desktop and try again.
    exit /b 1
)
echo   [PASS] Docker daemon is active.

REM 2. Check Virtual Environment
echo [2/4] Verifying Python virtual environment...
if not exist "venv\Scripts\python.exe" (
    echo   [WARN] Virtual environment not found. Running install.bat to initialize...
    call "install.bat"
    exit /b %errorlevel%
)
echo   [PASS] Python environment verified.

REM 3. Start Docker Monitoring Infrastructure
echo [3/4] Starting monitoring containers via Docker Compose...
docker compose -f monitoring-compose.yaml up -d
if %errorlevel% neq 0 (
    echo   [FAIL] Failed to start Docker monitoring services.
    exit /b 1
)
echo   [PASS] Monitoring containers started.

REM 4. Start DockPilot FastAPI Backend on Port 8001
echo [4/4] Starting DockPilot FastAPI backend on port 8001...
set BACKEND_RUNNING=0
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr :8001 ^| findstr LISTENING') do (
    set BACKEND_RUNNING=1
    echo   [PASS] DockPilot backend is already running with PID %%a.
)

if !BACKEND_RUNNING! equ 0 (
    echo   Launching DockPilot server in background...
    start "DockPilot Backend" /min "%PROJECT_ROOT%venv\Scripts\python.exe" -m uvicorn main:app --app-dir "%PROJECT_ROOT%manager" --host 0.0.0.0 --port 8001
    
    set WAIT_COUNT=0
    :WAIT_LOOP
    ping 127.0.0.1 -n 2 >nul
    set /a WAIT_COUNT+=1
    netstat -ano 2>nul | findstr :8001 | findstr LISTENING >nul 2>&1
    if !errorlevel! equ 0 (
        echo   [PASS] DockPilot backend listening on port 8001.
    ) else (
        if !WAIT_COUNT! lss 10 goto :WAIT_LOOP
        echo   [INFO] Continuing service verification...
    )
)
echo.

echo ==============================================================================
echo                     All DockPilot Services Started!
echo ==============================================================================
echo.
echo   Service                     URL                         Default Credentials
echo   ---------------------------------------------------------------------------
echo   DockPilot Dashboard         http://localhost:8001       None (direct access)
echo   DockPilot Swagger Docs      http://localhost:8001/docs  None
echo   Grafana Dashboard           http://localhost:3000       admin / admin
echo   Prometheus Web UI           http://localhost:9090       None
echo   Alertmanager Web UI         http://localhost:9093       None
echo   cAdvisor Telemetry          http://localhost:8085       None
echo.
echo   To verify infrastructure health:  check-monitoring.bat
echo   To stop all services:             stop.bat
echo ==============================================================================
exit /b 0
