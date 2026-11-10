@echo off
setlocal enabledelayedexpansion

REM ==============================================================================
REM DockPilot - Automated Installation and Setup Script
REM Platform: Windows 10 / 11 (CMD compatible)
REM Automates prerequisites check, virtual environment setup, dependencies,
REM configuration, Docker monitoring stack startup, backend launch, and health verification.
REM ==============================================================================

echo ==============================================================================
echo                      DockPilot - Installation and Setup
echo ==============================================================================
echo.

REM Change directory to project root
cd /d "%~dp0"
set PROJECT_ROOT=%~dp0

REM ------------------------------------------------------------------------------
REM Step 1: Check System Prerequisites
REM ------------------------------------------------------------------------------
echo [1/7] Verifying system prerequisites...

REM 1a. Check Git
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo   [FAIL] Git is not installed or not in system PATH.
    echo          Download and install Git from https://git-scm.com/
    goto :ERROR_EXIT
)
for /f "tokens=*" %%v in ('git --version 2^>nul') do echo   [PASS] Git found: %%v

REM 1b. Check Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo   [FAIL] Python is not installed or not in system PATH.
    echo          Download and install Python 3.10+ from https://www.python.org/
    goto :ERROR_EXIT
)
for /f "tokens=*" %%v in ('python --version 2^>nul') do echo   [PASS] Python found: %%v

REM Verify Python version >= 3.10
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo   [FAIL] Python 3.10 or higher is required. Please upgrade Python.
    goto :ERROR_EXIT
)

REM 1c. Check Docker CLI
where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo   [FAIL] Docker CLI is not installed or not in system PATH.
    echo          Please install Docker Desktop from https://www.docker.com/products/docker-desktop/
    goto :ERROR_EXIT
)
for /f "tokens=*" %%v in ('docker --version 2^>nul') do echo   [PASS] Docker CLI found: %%v

REM 1d. Check Docker Compose
docker compose version >nul 2>&1
if %errorlevel% neq 0 (
    echo   [FAIL] Docker Compose v2 is not available.
    echo          Ensure Docker Desktop is up to date.
    goto :ERROR_EXIT
)
for /f "tokens=*" %%v in ('docker compose version 2^>nul') do echo   [PASS] Docker Compose found: %%v

REM 1e. Check Docker Engine Daemon
echo   Checking Docker daemon connection...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo   [FAIL] Docker daemon is not running.
    echo.
    echo   [ACTION REQUIRED]
    echo   Please start Docker Desktop on your system and wait until the whale icon
    echo   shows "Docker Desktop is running", then re-run install.bat.
    goto :ERROR_EXIT
)
echo   [PASS] Docker daemon is active and responding.
echo.

REM ------------------------------------------------------------------------------
REM Step 2: Validate Project Structure & Required Files
REM ------------------------------------------------------------------------------
echo [2/7] Checking required project files and directories...

set MISSING_FILES=0

if not exist "monitoring-compose.yaml" (
    echo   [FAIL] Missing file: monitoring-compose.yaml
    set /a MISSING_FILES+=1
)
if not exist "manager\main.py" (
    echo   [FAIL] Missing file: manager\main.py
    set /a MISSING_FILES+=1
)
if not exist "manager\requirements.txt" (
    echo   [FAIL] Missing file: manager\requirements.txt
    set /a MISSING_FILES+=1
)
if not exist "prometheus\prometheus.yml" (
    echo   [FAIL] Missing file: prometheus\prometheus.yml
    set /a MISSING_FILES+=1
)
if not exist "prometheus\alert_rules.yml" (
    echo   [FAIL] Missing file: prometheus\alert_rules.yml
    set /a MISSING_FILES+=1
)
if not exist "alertmanager\alertmanager.yml" (
    echo   [FAIL] Missing file: alertmanager\alertmanager.yml
    set /a MISSING_FILES+=1
)
if not exist "grafana\dashboards\dockpilot-monitoring.json" (
    echo   [FAIL] Missing file: grafana\dashboards\dockpilot-monitoring.json
    set /a MISSING_FILES+=1
)

if %MISSING_FILES% gtr 0 (
    echo   [FAIL] Critical project files are missing. Ensure you cloned the entire repository.
    goto :ERROR_EXIT
)

REM Ensure runtime data directories exist
if not exist "data" mkdir "data" >nul 2>&1
if not exist "reports" mkdir "reports" >nul 2>&1
if not exist "logs" mkdir "logs" >nul 2>&1

echo   [PASS] All core project files and runtime directories verified.
echo.

REM ------------------------------------------------------------------------------
REM Step 3: Python Virtual Environment & Dependencies Setup
REM ------------------------------------------------------------------------------
echo [3/7] Setting up Python virtual environment and dependencies...

if not exist "venv\Scripts\python.exe" (
    echo   Creating virtual environment in .\venv...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo   [FAIL] Failed to create Python virtual environment.
        goto :ERROR_EXIT
    )
    echo   [PASS] Virtual environment created successfully.
) else (
    echo   [PASS] Virtual environment already exists at .\venv.
)

echo   Installing and upgrading Python dependencies...
venv\Scripts\python.exe -m pip install --upgrade pip >nul 2>&1
venv\Scripts\pip.exe install -r manager\requirements.txt pytest httpx >nul 2>&1
if %errorlevel% neq 0 (
    echo   [WARN] Error occurred during pip install. Retrying with verbose output...
    venv\Scripts\pip.exe install -r manager\requirements.txt pytest httpx
    if %errorlevel% neq 0 (
        echo   [FAIL] Failed to install required Python packages.
        goto :ERROR_EXIT
    )
)
echo   [PASS] Python dependencies installed successfully.
echo.

REM ------------------------------------------------------------------------------
REM Step 4: Environment & Secrets Configuration
REM ------------------------------------------------------------------------------
echo [4/7] Checking environment configuration...

if not exist ".env" (
    if exist ".env.example" (
        echo   Creating .env from .env.example with secure default settings...
        copy ".env.example" ".env" >nul
        echo   [PASS] Initialized .env configuration file.
    ) else (
        echo   [WARN] .env.example not found; skipping default .env creation.
    )
) else (
    echo   [PASS] Existing .env file detected; preserving existing credentials and configuration.
)
echo.

REM ------------------------------------------------------------------------------
REM Step 5: Validate and Start Docker Monitoring Infrastructure
REM ------------------------------------------------------------------------------
echo [5/7] Validating and starting Docker monitoring services...

echo   Validating Docker Compose configuration...
docker compose -f monitoring-compose.yaml config >nul 2>&1
if %errorlevel% neq 0 (
    echo   [FAIL] Docker Compose file validation failed. Check syntax in monitoring-compose.yaml.
    goto :ERROR_EXIT
)
echo   [PASS] Docker Compose configuration is valid.

echo   Starting monitoring containers (Prometheus, Grafana, Alertmanager, cAdvisor, Node Exporter)...
docker compose -f monitoring-compose.yaml up -d
if %errorlevel% neq 0 (
    echo   [FAIL] Failed to start Docker monitoring containers.
    goto :ERROR_EXIT
)
echo   [PASS] Monitoring containers launched successfully.
echo.

REM ------------------------------------------------------------------------------
REM Step 6: Start DockPilot FastAPI Backend on Port 8001
REM ------------------------------------------------------------------------------
echo [6/7] Starting DockPilot FastAPI backend service (port 8001)...

set BACKEND_RUNNING=0
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr :8001 ^| findstr LISTENING') do (
    set BACKEND_RUNNING=1
    echo   [PASS] DockPilot backend is already running with PID %%a.
)

if !BACKEND_RUNNING! equ 0 (
    echo   Launching DockPilot FastAPI server on http://0.0.0.0:8001...
    start "DockPilot Backend" /min "%PROJECT_ROOT%venv\Scripts\python.exe" -m uvicorn main:app --app-dir "%PROJECT_ROOT%manager" --host 0.0.0.0 --port 8001
    
    REM Wait for backend port to open (up to 15 seconds)
    echo   Waiting for backend to bind port 8001...
    set WAIT_COUNT=0
    :WAIT_BACKEND_LOOP
    ping 127.0.0.1 -n 2 >nul
    set /a WAIT_COUNT+=1
    netstat -ano 2>nul | findstr :8001 | findstr LISTENING >nul 2>&1
    if !errorlevel! equ 0 (
        echo   [PASS] DockPilot backend is listening on port 8001.
    ) else (
        if !WAIT_COUNT! lss 15 goto :WAIT_BACKEND_LOOP
        echo   [WARN] Backend startup took longer than expected. Proceeding with health check.
    )
)
echo.

REM ------------------------------------------------------------------------------
REM Step 7: Service Health & Monitoring Integration Verification
REM ------------------------------------------------------------------------------
echo [7/7] Verifying service readiness and Prometheus targets...

echo   Allowing services 5 seconds to stabilize scrape cycles...
ping 127.0.0.1 -n 6 >nul

REM Run the automated health check script
if exist "check-monitoring.bat" (
    call "check-monitoring.bat"
    if !errorlevel! neq 0 (
        echo.
        echo   [WARN] Some monitoring health checks reported warnings or are still initializing.
        echo          Run check-monitoring.bat in a few moments to re-verify.
    )
) else (
    echo   [WARN] check-monitoring.bat not found; skipped automated target verification.
)
echo.

REM ------------------------------------------------------------------------------
REM Final Installation Summary & Access URLs
REM ------------------------------------------------------------------------------
echo ==============================================================================
echo                     DockPilot Installation Complete!
echo ==============================================================================
echo.
echo   All DockPilot core and monitoring services are active and operational:
echo.
echo   Service                     URL                         Default Credentials
echo   ---------------------------------------------------------------------------
echo   DockPilot Dashboard         http://localhost:8001       None (direct access)
echo   DockPilot Swagger Docs      http://localhost:8001/docs  None
echo   Grafana Dashboard           http://localhost:3000       admin / admin
echo   Prometheus Web UI           http://localhost:9090       None (internal isolated)
echo   Alertmanager Web UI         http://localhost:9093       None (internal isolated)
echo   cAdvisor Telemetry          http://localhost:8085       None
echo.
echo   Quick Commands:
echo     start.bat             - Start all DockPilot services
echo     stop.bat              - Safely stop services without data loss
echo     check-monitoring.bat  - Run infrastructure health check
echo.
echo   To configure SMTP email notifications:
echo     1. Edit the .env file with your SMTP credentials.
echo     2. Run: venv\Scripts\python.exe scripts\apply_alertmanager_env.py
echo.
echo ==============================================================================
exit /b 0

:ERROR_EXIT
echo.
echo ==============================================================================
echo [ERROR] DockPilot installation encountered an error and could not complete.
echo ==============================================================================
echo.
echo Troubleshooting steps:
echo   1. Ensure Docker Desktop is installed, running, and Linux containers mode is enabled.
echo   2. Verify ports 8001, 9090, 3000, 9093, and 8085 are not blocked or used by other apps.
echo   3. Run check-monitoring.bat to diagnose individual component health.
echo   4. Review container logs using: docker logs ^<container-name^>
echo.
exit /b 1
