@echo off
setlocal enabledelayedexpansion

REM ==============================================================================
REM DockPilot Monitoring Infrastructure Health Check Script
REM Checks container statuses, target health, metric availability, Grafana,
REM and Prometheus alert rule evaluation readiness
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
echo [1/12] Checking Docker daemon status...
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
echo [2/12] Checking dockpilot-prometheus container status...
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
echo [3/12] Checking dockpilot-cadvisor container status...
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
echo [4/12] Checking dockpilot-node-exporter container status...
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
echo [5/12] Checking Prometheus HTTP endpoint: http://localhost:9090/-/healthy...
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
echo [6/12] Checking Prometheus target health status...

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

REM 6d. Grafana target
curl.exe -s --get "http://localhost:9090/api/v1/query" --data-urlencode "query=up{job='grafana'}" 2>nul | findstr /c:"\"1\"" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Target 'grafana' is UP.
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Target 'grafana' is DOWN or missing.
    set /a FAIL_COUNT+=1
)

REM 6e. DockPilot exporter target
curl.exe -s --get "http://localhost:9090/api/v1/query" --data-urlencode "query=up{job='dockpilot'}" 2>nul | findstr /c:"\"1\"" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Target 'dockpilot' is UP.
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Target 'dockpilot' is DOWN or missing.
    set /a FAIL_COUNT+=1
)

REM 6f. Alertmanager target
curl.exe -s --get "http://localhost:9090/api/v1/query" --data-urlencode "query=up{job='alertmanager'}" 2>nul | findstr /c:"\"1\"" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Target 'alertmanager' is UP.
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Target 'alertmanager' is DOWN or missing.
    set /a FAIL_COUNT+=1
)
echo.

REM ------------------------------------------------------------------------------
REM Check 7: Node Exporter Metrics Availability
REM ------------------------------------------------------------------------------
echo [7/12] Checking Node Exporter metrics availability...

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
echo [8/12] Checking cAdvisor metrics and dashboard...

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
REM Check 9: Grafana Container Status & Health
REM ------------------------------------------------------------------------------
echo [9/12] Checking dockpilot-grafana container status and health...

REM 9a. Grafana container running
docker ps -f name=^dockpilot-grafana$ -f status=running -q | findstr /r "." >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Container 'dockpilot-grafana' is running.
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Container 'dockpilot-grafana' is not running.
    set /a FAIL_COUNT+=1
)

REM 9b. Grafana HTTP health endpoint
curl.exe -s -f http://localhost:3000/api/health >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Grafana HTTP health endpoint [http://localhost:3000/api/health] responded [HTTP 200].
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Grafana HTTP health endpoint is not reachable or unhealthy.
    set /a FAIL_COUNT+=1
)
echo.

REM ------------------------------------------------------------------------------
REM Check 10: Grafana Provisioning & Dashboard Readiness
REM ------------------------------------------------------------------------------
echo [10/12] Checking Grafana provisioning and dashboard availability...

REM 10a. Prometheus Datasource Provisioning Check
curl.exe -s -u admin:admin http://localhost:3000/api/datasources/uid/prometheus/health 2>nul | findstr /c:"\"status\":\"OK\"" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Grafana Prometheus datasource is provisioned and healthy [status: OK].
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Grafana Prometheus datasource is not healthy or missing.
    set /a FAIL_COUNT+=1
)

REM 10b. Dashboard Provisioning Check
curl.exe -s -u admin:admin http://localhost:3000/api/dashboards/uid/dockpilot-monitoring 2>nul | findstr /c:"dockpilot-monitoring" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Grafana DockPilot monitoring dashboard is auto-provisioned and accessible.
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Grafana DockPilot monitoring dashboard is missing or not provisioned.
    set /a FAIL_COUNT+=1
)
echo.

REM ------------------------------------------------------------------------------
REM Check 11: Prometheus Alert Rules & Alert Evaluation Readiness
REM ------------------------------------------------------------------------------
echo [11/12] Checking Prometheus alert rules and evaluation status...

REM 11a. Alert rules loaded in Prometheus
curl.exe -s http://localhost:9090/api/v1/rules 2>nul | findstr /c:"dockpilot_infrastructure_alerts" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Prometheus alert rules file 'alert_rules.yml' is loaded.
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Prometheus alert rules file 'alert_rules.yml' is not loaded.
    set /a FAIL_COUNT+=1
)

REM 11b. Alert rule evaluation health
curl.exe -s http://localhost:9090/api/v1/rules 2>nul | findstr /c:"\"health\":\"ok\"" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Prometheus alert rules are evaluating successfully without errors [health: ok].
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Prometheus alert rules evaluation encountered errors.
    set /a FAIL_COUNT+=1
)

REM 11c. Prometheus ALERTS time-series query
curl.exe -s --get "http://localhost:9090/api/v1/query" --data-urlencode "query=ALERTS" 2>nul | findstr /c:"\"status\":\"success\"" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Prometheus ALERTS evaluation pipeline is active and responding.
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Prometheus ALERTS query failed.
    set /a FAIL_COUNT+=1
)

REM 11d. Custom Container Health metric scraped
curl.exe -s --get "http://localhost:9090/api/v1/query" --data-urlencode "query=dockpilot_container_health_status" 2>nul | findstr /c:"dockpilot_container_health_status" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Custom metric 'dockpilot_container_health_status' is actively scraped by Prometheus.
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Custom metric 'dockpilot_container_health_status' is missing in Prometheus.
    set /a FAIL_COUNT+=1
)
echo.

REM ------------------------------------------------------------------------------
REM Check 12: Alertmanager Service & Alert Delivery Readiness
REM ------------------------------------------------------------------------------
echo [12/12] Checking Alertmanager service and delivery readiness...

REM 12a. Alertmanager container status
docker ps -f name=^dockpilot-alertmanager$ -f status=running -q | findstr /r "." >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Container 'dockpilot-alertmanager' is running.
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Container 'dockpilot-alertmanager' is not running.
    set /a FAIL_COUNT+=1
)

REM 12b. Alertmanager health endpoint
curl.exe -s -f http://localhost:9093/-/healthy >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Alertmanager health endpoint [http://localhost:9093/-/healthy] responded [HTTP 200].
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Alertmanager health endpoint is not reachable or unhealthy.
    set /a FAIL_COUNT+=1
)

REM 12c. Alertmanager web interface
curl.exe -s -f http://localhost:9093/ >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Alertmanager web interface [http://localhost:9093] is accessible [HTTP 200].
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Alertmanager web interface is not accessible.
    set /a FAIL_COUNT+=1
)

REM 12d. Prometheus connected to Alertmanager
curl.exe -s http://localhost:9090/api/v1/alertmanagers 2>nul | findstr /c:"alertmanager:9093" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Prometheus is successfully connected to Alertmanager [alertmanager:9093].
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Prometheus is not connected to Alertmanager.
    set /a FAIL_COUNT+=1
)

REM 12e. Alertmanager configuration loaded
curl.exe -s http://localhost:9093/api/v2/status 2>nul | findstr /c:"dockpilot" >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Alertmanager active configuration is loaded successfully.
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Alertmanager configuration failed to load.
    set /a FAIL_COUNT+=1
)

REM 12f. Alert delivery configuration validity
docker run --rm -v "%CD%\alertmanager\alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro" --entrypoint /bin/amtool prom/alertmanager:latest check-config /etc/alertmanager/alertmanager.yml >nul 2>&1
if %errorlevel% equ 0 (
    echo   [PASS] Alertmanager configuration syntax and routing validated [amtool: SUCCESS].
    set /a PASS_COUNT+=1
) else (
    echo   [FAIL] Alertmanager configuration validation failed.
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
