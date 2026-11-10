@echo off
setlocal enabledelayedexpansion

REM ==============================================================================
REM DockPilot Monitoring Infrastructure Health Check Script
REM Checks container statuses, target health, and metric availability
REM Compatible with Windows Command Prompt (cmd.exe)
REM ==============================================================================

echo ==============================================================================
echo               DockPilot Monitoring Infrastructure Health Check
echo ==============================================================================
echo.

set PASS_COUNT=0
set FAIL_COUNT=0

REM ------------------------------------------------------------------------------
REM Check 1: Docker Daemon Status
REM ------------------------------------------------------------------------------
echo [1/8] Checking Docker daemon status...
docker info >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Docker daemon is running and accessible.
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Docker daemon is not running or not accessible.
    set /a FAIL_COUNT+=1
    goto :SUMMARY
)
echo.

REM ------------------------------------------------------------------------------
REM Check 2: Prometheus Container Status
REM ------------------------------------------------------------------------------
echo [2/8] Checking dockpilot-prometheus container status...
docker ps -f name=^dockpilot-prometheus$ -f status=running -q | findstr /r "." >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Container 'dockpilot-prometheus' is running.
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Container 'dockpilot-prometheus' is not running.
    set /a FAIL_COUNT+=1
)
echo.

REM ------------------------------------------------------------------------------
REM Check 3: cAdvisor Container Status
REM ------------------------------------------------------------------------------
echo [3/8] Checking dockpilot-cadvisor container status...
docker ps -f name=^dockpilot-cadvisor$ -f status=running -q | findstr /r "." >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Container 'dockpilot-cadvisor' is running.
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Container 'dockpilot-cadvisor' is not running.
    set /a FAIL_COUNT+=1
)
echo.

REM ------------------------------------------------------------------------------
REM Check 4: Node Exporter Container Status
REM ------------------------------------------------------------------------------
echo [4/8] Checking dockpilot-node-exporter container status...
docker ps -f name=^dockpilot-node-exporter$ -f status=running -q | findstr /r "." >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Container 'dockpilot-node-exporter' is running.
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Container 'dockpilot-node-exporter' is not running.
    set /a FAIL_COUNT+=1
)
echo.

REM ------------------------------------------------------------------------------
REM Check 5: Prometheus Server Readiness
REM ------------------------------------------------------------------------------
echo [5/8] Checking Prometheus HTTP endpoint: http://localhost:9090/-/healthy...
curl.exe -s -f http://localhost:9090/-/healthy >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Prometheus server is healthy [HTTP 200].
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Prometheus server is not reachable or unhealthy.
    set /a FAIL_COUNT+=1
)
echo.

REM ------------------------------------------------------------------------------
REM Check 6: Prometheus Target Health
REM ------------------------------------------------------------------------------
echo [6/8] Checking Prometheus target health status...

REM 6a. Prometheus target
curl.exe -s --get "http://localhost:9090/api/v1/query" --data-urlencode "query=up{job='prometheus'}" 2>nul | findstr /c:"\"1\"" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Target 'prometheus' is UP.
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Target 'prometheus' is DOWN or missing.
    set /a FAIL_COUNT+=1
)

REM 6b. cAdvisor target
curl.exe -s --get "http://localhost:9090/api/v1/query" --data-urlencode "query=up{job='cadvisor'}" 2>nul | findstr /c:"\"1\"" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Target 'cadvisor' is UP.
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Target 'cadvisor' is DOWN or missing.
    set /a FAIL_COUNT+=1
)

REM 6c. Node Exporter target
curl.exe -s --get "http://localhost:9090/api/v1/query" --data-urlencode "query=up{job='node-exporter'}" 2>nul | findstr /c:"\"1\"" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Target 'node-exporter' is UP.
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Target 'node-exporter' is DOWN or missing.
    set /a FAIL_COUNT+=1
)
echo.

REM ------------------------------------------------------------------------------
REM Check 7: Node Exporter Metrics Availability
REM ------------------------------------------------------------------------------
echo [7/8] Checking Node Exporter metrics availability...

REM 7a. Direct metrics scrape inside container
docker exec dockpilot-node-exporter wget -qO- http://localhost:9100/metrics 2>nul | findstr /c:"node_cpu_seconds_total" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Direct internal metrics endpoint [port 9100] is responding.
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Direct internal metrics endpoint [port 9100] failed to respond.
    set /a FAIL_COUNT+=1
)

REM 7b. node_cpu_seconds_total via Prometheus
curl.exe -s --get "http://localhost:9090/api/v1/query" --data-urlencode "query=node_cpu_seconds_total" 2>nul | findstr /c:"node_cpu_seconds_total" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Metric 'node_cpu_seconds_total' is scraped by Prometheus.
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Metric 'node_cpu_seconds_total' is missing in Prometheus.
    set /a FAIL_COUNT+=1
)

REM 7c. node_memory_MemAvailable_bytes via Prometheus
curl.exe -s --get "http://localhost:9090/api/v1/query" --data-urlencode "query=node_memory_MemAvailable_bytes" 2>nul | findstr /c:"node_memory_MemAvailable_bytes" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Metric 'node_memory_MemAvailable_bytes' is scraped by Prometheus.
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Metric 'node_memory_MemAvailable_bytes' is missing in Prometheus.
    set /a FAIL_COUNT+=1
)
echo.

REM ------------------------------------------------------------------------------
REM Check 8: cAdvisor Metrics and Dashboard
REM ------------------------------------------------------------------------------
echo [8/8] Checking cAdvisor metrics and dashboard...

REM 8a. container_cpu_usage_seconds_total via Prometheus
curl.exe -s --get "http://localhost:9090/api/v1/query" --data-urlencode "query=container_cpu_usage_seconds_total" 2>nul | findstr /c:"container_cpu_usage_seconds_total" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Metric 'container_cpu_usage_seconds_total' is scraped by Prometheus.
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Metric 'container_cpu_usage_seconds_total' is missing in Prometheus.
    set /a FAIL_COUNT+=1
)

REM 8b. cAdvisor web dashboard HTTP 200
curl.exe -s -f http://localhost:8085/containers/ >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] cAdvisor web dashboard [http://localhost:8085] is accessible [HTTP 200].
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] cAdvisor web dashboard is not reachable or returned an error.
    set /a FAIL_COUNT+=1
)
echo.

REM ------------------------------------------------------------------------------
REM Summary
REM ------------------------------------------------------------------------------
:SUMMARY
echo ==============================================================================
echo Health Check Summary: %PASS_COUNT% Passed, %FAIL_COUNT% Failed
echo ==============================================================================

if %FAIL_COUNT% equ 0 (
    echo [RESULT] PASS - All monitoring infrastructure checks passed successfully!
    exit /b 0
) else (
    echo [RESULT] FAIL - One or more monitoring infrastructure checks failed.
    exit /b 1
)
