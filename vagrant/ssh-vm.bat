@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo  DockPilot - SSH into Linux VM Sandbox
echo ============================================================

where vagrant >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Vagrant is not installed or not found in system PATH.
    exit /b 1
)

cd /d "%~dp0\.."
vagrant ssh
