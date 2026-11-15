@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo  DockPilot - Optional Linux VM Sandbox Launcher
echo ============================================================

where vagrant >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Vagrant is not installed or not found in system PATH.
    echo.
    echo To use the optional Linux VM sandbox:
    echo 1. Install VirtualBox: https://www.virtualbox.org/
    echo 2. Install Vagrant:    https://developer.hashicorp.com/vagrant/downloads
    echo.
    echo Note: DockPilot runs natively on Windows Docker Desktop without Vagrant.
    exit /b 1
)

cd /d "%~dp0\.."

echo [*] Starting / Provisioning DockPilot Linux VM (VirtualBox)...
echo [*] Resource configuration: 2 vCPUs, 2048 MB RAM (optimized for 8 GB RAM hosts)
vagrant up

if %ERRORLEVEL% equ 0 (
    echo.
    echo ============================================================
    echo  DockPilot VM is running!
    echo ============================================================
    echo  DockPilot Dashboard:  http://localhost:8001
    echo  Grafana:              http://localhost:3000 (admin/admin)
    echo  Prometheus:           http://localhost:9090
    echo  Alertmanager:         http://localhost:9093
    echo  cAdvisor:             http://localhost:8085
    echo ============================================================
) else (
    echo [ERROR] Failed to start DockPilot Vagrant VM.
    exit /b 1
)
