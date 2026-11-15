@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo  DockPilot - Linux VM Sandbox Status
echo ============================================================

where vagrant >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Vagrant is not installed or not found in system PATH.
    exit /b 1
)

cd /d "%~dp0\.."
vagrant status
