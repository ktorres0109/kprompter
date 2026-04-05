# KPrompter — Windows Installer
# Run: irm https://raw.githubusercontent.com/ktorres0109/kprompter/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

$REPO = "https://github.com/ktorres0109/kprompter"
$INSTALL_DIR = "$env:LOCALAPPDATA\KPrompter"
$VENV = "$INSTALL_DIR\.venv"

Write-Host ""
Write-Host "  K> KPrompter Installer" -ForegroundColor Cyan
Write-Host "  Prompt optimizer for every AI -- one hotkey away" -ForegroundColor DarkGray
Write-Host ""

# Check Python
try {
    $pyver = python --version 2>&1
    Write-Host "  Python: $pyver" -ForegroundColor Cyan
} catch {
    Write-Host "  Python not found. Install Python 3.9+ from python.org" -ForegroundColor Red
    exit 1
}

# Clone or update
if (Test-Path "$INSTALL_DIR\.git") {
    Write-Host "  Updating existing install..."
    git -C $INSTALL_DIR pull --quiet
} else {
    Write-Host "  Cloning KPrompter..."
    git clone --quiet $REPO $INSTALL_DIR
}

# Virtualenv
Write-Host "  Creating virtual environment..."
python -m venv $VENV

# Install deps
Write-Host "  Installing dependencies..."
& "$VENV\Scripts\pip.exe" install --quiet --upgrade pip
& "$VENV\Scripts\pip.exe" install --quiet -r "$INSTALL_DIR\requirements.txt"

# Create launcher batch file
$launcher = "$env:LOCALAPPDATA\Microsoft\WindowsApps\kprompter.bat"
@"
@echo off
"$VENV\Scripts\python.exe" "$INSTALL_DIR\main.py" %*
"@ | Set-Content $launcher

Write-Host ""
Write-Host "  KPrompter installed." -ForegroundColor Green
Write-Host "  Run: kprompter" -ForegroundColor Cyan
Write-Host ""
Write-Host "  To start on login, press Win+R -> shell:startup -> create a shortcut to kprompter.bat" -ForegroundColor DarkGray
Write-Host ""
