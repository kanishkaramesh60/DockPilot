@echo off
setlocal enabledelayedexpansion

REM ==============================================================================
REM DockPilot - Automated Setup and Environment Provisioning
REM Platform: Windows 10 / 11 (CMD compatible)
REM ==============================================================================

echo ==============================================================================
echo                      DockPilot - Environment Setup
echo ==============================================================================
echo.

cd /d "%~dp0\.."
set "PROJECT_ROOT=%cd%"

REM ------------------------------------------------------------------------------
REM Step 1: Check System Prerequisites
REM ------------------------------------------------------------------------------
echo [1/6] Verifying system prerequisites...

where git >nul 2>&1
if %errorlevel% neq 0 (
    echo   [FAIL] Git is not installed or not in system PATH.
    echo          Please install Git from https://git-scm.com/
    exit /b 1
)
for /f "tokens=*" %%v in ('git --version 2^>nul') do echo   [PASS] Git found: %%v

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo   [FAIL] Python is not installed or not in system PATH.
    echo          Please install Python 3.10+ from https://www.python.org/
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>nul') do echo   [PASS] Python found: %%v

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo   [FAIL] Python 3.10 or higher is required.
    exit /b 1
)

where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo   [FAIL] Docker CLI is not installed or not in system PATH.
    echo          Please install Docker Desktop: https://www.docker.com/products/docker-desktop/
    exit /b 1
)
for /f "tokens=*" %%v in ('docker --version 2^>nul') do echo   [PASS] Docker CLI found: %%v

docker compose version >nul 2>&1
if %errorlevel% neq 0 (
    echo   [FAIL] Docker Compose v2 is not available.
    exit /b 1
)
for /f "tokens=*" %%v in ('docker compose version 2^>nul') do echo   [PASS] Docker Compose found: %%v

echo   Checking Docker Engine connectivity...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo   [FAIL] Docker Engine daemon is not running.
    echo          Please start Docker Desktop and wait until it is running.
    exit /b 1
)
echo   [PASS] Docker Engine daemon is active and responding.
echo.

REM ------------------------------------------------------------------------------
REM Step 2: Setup Python Virtual Environment
REM ------------------------------------------------------------------------------
echo [2/6] Validating Python virtual environment...

set "PYTHON_EXE="
set "VENV_DIR="

if exist "%PROJECT_ROOT%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
    set "VENV_DIR=%PROJECT_ROOT%\.venv"
    echo   [PASS] Existing virtual environment detected: .venv
) else if exist "%PROJECT_ROOT%\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%PROJECT_ROOT%\venv\Scripts\python.exe"
    set "VENV_DIR=%PROJECT_ROOT%\venv"
    echo   [PASS] Existing virtual environment detected: venv
) else (
    echo   [INFO] Creating new virtual environment at .venv...
    python -m venv "%PROJECT_ROOT%\.venv"
    if !errorlevel! neq 0 (
        echo   [FAIL] Failed to create virtual environment.
        exit /b 1
    )
    set "PYTHON_EXE=%PROJECT_ROOT%\.venv\Scripts\python.exe"
    set "VENV_DIR=%PROJECT_ROOT%\.venv"
    echo   [PASS] Virtual environment created successfully.
)

REM ------------------------------------------------------------------------------
REM Step 3: Install Required Dependencies
REM ------------------------------------------------------------------------------
echo [3/6] Installing / updating Python dependencies...
"%PYTHON_EXE%" -m pip install --upgrade pip --quiet
if exist "%PROJECT_ROOT%\requirements.txt" (
    "%PYTHON_EXE%" -m pip install -r "%PROJECT_ROOT%\requirements.txt" --quiet
) else if exist "%PROJECT_ROOT%\manager\requirements.txt" (
    "%PYTHON_EXE%" -m pip install -r "%PROJECT_ROOT%\manager\requirements.txt" --quiet
) else (
    "%PYTHON_EXE%" -m pip install fastapi uvicorn[standard] docker psutil PyYAML requests python-dotenv pytest httpx --quiet
)
if %errorlevel% neq 0 (
    echo   [FAIL] Error installing Python dependencies.
    exit /b 1
)
echo   [PASS] Dependencies installed successfully (including psutil, fastapi, docker).
echo.

REM ------------------------------------------------------------------------------
REM Step 4: Environment Configuration & Directory Setup
REM ------------------------------------------------------------------------------
echo [4/6] Checking configuration files and directories...

if not exist "%PROJECT_ROOT%\data" mkdir "%PROJECT_ROOT%\data"
if not exist "%PROJECT_ROOT%\reports" mkdir "%PROJECT_ROOT%\reports"
if not exist "%PROJECT_ROOT%\logs" mkdir "%PROJECT_ROOT%\logs"

if not exist "%PROJECT_ROOT%\.env" (
    if exist "%PROJECT_ROOT%\.env.example" (
        copy "%PROJECT_ROOT%\.env.example" "%PROJECT_ROOT%\.env" >nul
        echo   [PASS] Created .env from .env.example
    ) else (
        echo   [WARN] No .env.example found; creating default .env
        echo BACKEND_PORT=8001 > "%PROJECT_ROOT%\.env"
    )
) else (
    echo   [PASS] Existing .env file preserved.
)

REM Validate all configurations with Python validator
"%PYTHON_EXE%" "%PROJECT_ROOT%\scripts\validate_environment.py"
if %errorlevel% neq 0 (
    echo   [FAIL] Configuration validation encountered errors.
    exit /b 1
)
echo.

REM ------------------------------------------------------------------------------
REM Step 5: Start Docker Monitoring Stack
REM ------------------------------------------------------------------------------
echo [5/6] Starting Docker monitoring infrastructure...
docker compose -f "%PROJECT_ROOT%\monitoring-compose.yaml" up -d
if %errorlevel% neq 0 (
    echo   [FAIL] Failed to start Docker monitoring services.
    exit /b 1
)
echo   [PASS] Monitoring containers running (Prometheus, Grafana, Alertmanager, cAdvisor, Node Exporter).
echo.

REM ------------------------------------------------------------------------------
REM Step 6: Start DockPilot Backend & Verify
REM ------------------------------------------------------------------------------
echo [6/6] Starting DockPilot FastAPI backend on port 8001...
set BACKEND_RUNNING=0
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr :8001 ^| findstr LISTENING') do (
    set BACKEND_RUNNING=1
    echo   [PASS] DockPilot backend is already running on port 8001 (PID: %%a).
)

if !BACKEND_RUNNING! equ 0 (
    echo   Launching backend process in background...
    start "DockPilot Backend" /min "%PYTHON_EXE%" -m uvicorn main:app --app-dir "%PROJECT_ROOT%\manager" --host 0.0.0.0 --port 8001
    
    set WAIT_COUNT=0
    :WAIT_BACKEND
    ping 127.0.0.1 -n 2 >nul
    set /a WAIT_COUNT+=1
    netstat -ano 2>nul | findstr :8001 | findstr LISTENING >nul 2>&1
    if !errorlevel! equ 0 (
        echo   [PASS] DockPilot backend listening on port 8001.
    ) else (
        if !WAIT_COUNT! lss 10 goto :WAIT_BACKEND
        echo   [WARN] Backend startup taking longer than expected.
    )
)
echo.

echo ==============================================================================
echo                     DockPilot Setup Completed Successfully!
echo ==============================================================================
echo.
echo   Service                     URL                         Default Credentials
echo   ---------------------------------------------------------------------------
echo   DockPilot Dashboard         http://localhost:8001       None (Unified Cockpit)
echo   DockPilot Swagger Docs      http://localhost:8001/docs  None
echo   Grafana Dashboard           http://localhost:3000       admin / admin
echo   Prometheus Web UI           http://localhost:9090       None
echo   Alertmanager Web UI         http://localhost:9093       None
echo   cAdvisor Telemetry          http://localhost:8085       None
echo.
echo   Management Commands:
echo     Start services:     scripts\start-dockpilot.bat
echo     Stop services:      scripts\stop-dockpilot.bat
echo     Verify health:      scripts\verify-dockpilot.bat
echo ==============================================================================
exit /b 0
