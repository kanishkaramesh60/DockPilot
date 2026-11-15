@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo  DockPilot - Stop Linux VM Sandbox
echo ============================================================

where vagrant >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Vagrant is not installed or not found in system PATH.
    exit /b 1
)

cd /d "%~dp0\.."
echo [*] Gracefully shutting down DockPilot VM...
vagrant halt
if %ERRORLEVEL% equ 0 (
    echo [OK] DockPilot VM stopped cleanly.
) else (
    echo [ERROR] Failed to stop DockPilot VM.
    exit /b 1
)
