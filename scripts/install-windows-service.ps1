# install-windows-service.ps1 — Install Captivity as a Windows Service
#
# Usage (elevated PowerShell):
#   .\scripts\install-windows-service.ps1
#
# Requires: Python, pip, pywin32

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$ServiceName = "CaptivityDaemon"
$DisplayName = "Captivity — Autonomous Captive Portal Client"
$Description = "Automatically detects and logs into captive WiFi portals."

# --- Preflight ---

Write-Host "=== Captivity Windows Service Installer ===" -ForegroundColor Cyan

$pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonPath) {
    Write-Error "Python not found on PATH. Install Python 3.8+ first."
    exit 1
}

Write-Host "Python: $pythonPath"

# Ensure pywin32 is installed
try {
    python -c "import win32serviceutil" 2>$null
} catch {
    Write-Host "Installing pywin32..." -ForegroundColor Yellow
    pip install "pywin32>=306"
}

# Ensure captivity is installed
$captivityPath = (Get-Command captivity -ErrorAction SilentlyContinue).Source
if (-not $captivityPath) {
    Write-Error "'captivity' CLI not found. Install with: pip install -e ."
    exit 1
}

Write-Host "Captivity: $captivityPath"

# --- Find the win_service module ---

$winServiceModule = python -c "import captivity.daemon.win_service; print(captivity.daemon.win_service.__file__)" 2>$null
if (-not $winServiceModule) {
    Write-Error "Could not locate captivity.daemon.win_service module."
    exit 1
}

Write-Host "Service module: $winServiceModule"

# --- Remove existing service (if any) ---

$existing = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Stopping and removing existing service..." -ForegroundColor Yellow
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    python $winServiceModule remove 2>$null
    Start-Sleep -Seconds 2
}

# --- Install ---

Write-Host "Installing service..." -ForegroundColor Green
python $winServiceModule install

# Set description
Set-Service -Name $ServiceName -Description $Description -StartupType Automatic

# --- Start ---

Write-Host "Starting service..." -ForegroundColor Green
Start-Service -Name $ServiceName

Write-Host ""
Write-Host "=== Installation Complete ===" -ForegroundColor Green
Write-Host "Service: $ServiceName"
Write-Host "Status:  $((Get-Service -Name $ServiceName).Status)"
Write-Host ""
Write-Host "Management commands:"
Write-Host "  Get-Service $ServiceName          # Check status"
Write-Host "  Stop-Service $ServiceName          # Stop"
Write-Host "  Start-Service $ServiceName         # Start"
Write-Host "  python $winServiceModule remove    # Uninstall"
