# KPrompter — Windows Installer
# Run in PowerShell (Admin recommended):
#   irm https://raw.githubusercontent.com/ktorres0109/kprompter/main/install.ps1 | iex

$ErrorActionPreference = "Stop"
$REPO      = "https://github.com/ktorres0109/kprompter"
$INSTALL   = "$env:LOCALAPPDATA\KPrompter"
$VENV      = "$INSTALL\.venv"
$LAUNCHER  = "$env:LOCALAPPDATA\Microsoft\WindowsApps\kprompter.bat"

function Write-Step($msg) { Write-Host "  $msg" -ForegroundColor Cyan }
function Write-Dim($msg)  { Write-Host "  $msg" -ForegroundColor DarkGray }
function Write-Ok($msg)   { Write-Host "  $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  $msg" -ForegroundColor Yellow }

Write-Host ""
Write-Host "  K> KPrompter Installer" -ForegroundColor Cyan
Write-Host "  Prompt optimizer for every AI -- one hotkey away" -ForegroundColor DarkGray
Write-Host ""

# ── Check Python ──────────────────────────────────────────────────────────────
Write-Step "Checking Python..."
$pyCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3\.(\d+)") {
            $minor = [int]$Matches[1]
            if ($minor -ge 9) { $pyCmd = $cmd; break }
        }
    } catch {}
}

if (-not $pyCmd) {
    Write-Warn "Python 3.9+ not found."
    Write-Warn "Install it from: https://python.org/downloads"
    Write-Warn "Make sure to check 'Add Python to PATH' during install."
    exit 1
}
Write-Step "Python: $(& $pyCmd --version)"

# ── Check / install Git ───────────────────────────────────────────────────────
Write-Step "Checking Git..."
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Warn "Git not found. Installing via winget..."
    winget install --id Git.Git -e --source winget --silent
    $env:PATH += ";$env:ProgramFiles\Git\cmd"
}

# ── Clone or update ───────────────────────────────────────────────────────────
if (Test-Path "$INSTALL\.git") {
    Write-Step "Updating existing install..."
    git -C $INSTALL pull --quiet
} else {
    Write-Step "Cloning KPrompter..."
    git clone --quiet $REPO $INSTALL
}

# ── Venv + deps ───────────────────────────────────────────────────────────────
Write-Step "Creating virtual environment..."
& $pyCmd -m venv $VENV

Write-Step "Installing dependencies..."
& "$VENV\Scripts\pip.exe" install --quiet --upgrade pip
& "$VENV\Scripts\pip.exe" install --quiet -r "$INSTALL\requirements.txt"

# ── Launcher batch file ───────────────────────────────────────────────────────
$launcherContent = "@echo off`r`n`"$VENV\Scripts\python.exe`" `"$INSTALL\main.py`" %*`r`n"
[System.IO.File]::WriteAllText($LAUNCHER, $launcherContent)
Write-Step "Launcher created: kprompter"

# ── Startup shortcut ──────────────────────────────────────────────────────────
$startupDir = [Environment]::GetFolderPath("Startup")
$shortcut = "$startupDir\KPrompter.lnk"
$wsh = New-Object -ComObject WScript.Shell
$lnk = $wsh.CreateShortcut($shortcut)
$lnk.TargetPath  = $LAUNCHER
$lnk.Description = "KPrompter — AI prompt optimizer"
$lnk.Save()
Write-Step "Added to Windows startup"

Write-Host ""
Write-Ok "KPrompter installed."
Write-Host "  Run: " -NoNewline
Write-Host "kprompter" -ForegroundColor Cyan
Write-Host ""
Write-Warn "Note: pynput needs uiautomation access for global hotkeys."
Write-Warn "If the hotkey doesn't work, run KPrompter as Administrator once."
Write-Host ""
