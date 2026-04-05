#!/usr/bin/env bash
# KPrompter — one-line installer for macOS and Linux
# Usage: curl -sSL https://raw.githubusercontent.com/ktorres0109/kprompter/main/install.sh | bash

set -e

REPO="https://github.com/ktorres0109/kprompter"
INSTALL_DIR="$HOME/.local/share/kprompter"
BIN_LINK="$HOME/.local/bin/kprompter"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
DIM='\033[2m'
RESET='\033[0m'
BOLD='\033[1m'

echo ""
echo -e "${CYAN}${BOLD}  K> KPrompter Installer${RESET}"
echo -e "${DIM}  Prompt optimizer for every AI — one hotkey away${RESET}"
echo ""

# ── Detect OS ────────────────────────────────────────────────────────────────
OS="$(uname -s)"
case "$OS" in
  Darwin) PLATFORM="macOS" ;;
  Linux)  PLATFORM="Linux" ;;
  *)      echo -e "${RED}Unsupported OS: $OS. Use install.ps1 on Windows.${RESET}"; exit 1 ;;
esac
echo -e "  Platform: ${CYAN}$PLATFORM${RESET}"

# ── Linux: detect distro and install system deps ──────────────────────────────
if [ "$PLATFORM" = "Linux" ]; then
  echo -e "  Checking system dependencies…"

  if command -v pacman &>/dev/null; then
    # Arch / Manjaro
    echo -e "  ${DIM}Detected: Arch Linux${RESET}"
    sudo pacman -S --needed --noconfirm python python-pip xclip xdotool tk 2>/dev/null || true
  elif command -v apt-get &>/dev/null; then
    # Debian / Ubuntu
    echo -e "  ${DIM}Detected: Debian/Ubuntu${RESET}"
    sudo apt-get update -qq
    sudo apt-get install -y python3 python3-pip python3-venv xclip xdotool python3-tk 2>/dev/null || true
  elif command -v dnf &>/dev/null; then
    # Fedora
    echo -e "  ${DIM}Detected: Fedora${RESET}"
    sudo dnf install -y python3 python3-pip xclip xdotool python3-tkinter 2>/dev/null || true
  elif command -v zypper &>/dev/null; then
    # openSUSE
    echo -e "  ${DIM}Detected: openSUSE${RESET}"
    sudo zypper install -y python3 python3-pip xclip xdotool python3-tk 2>/dev/null || true
  else
    echo -e "  ${YELLOW}Could not detect package manager. Make sure xclip, xdotool, and python3-tk are installed.${RESET}"
  fi
fi

# ── Check Python ──────────────────────────────────────────────────────────────
if command -v python3 &>/dev/null; then
  PYTHON=python3
elif command -v python &>/dev/null; then
  PYTHON=python
else
  echo -e "${RED}Python 3 not found. Install Python 3.9+ first.${RESET}"
  exit 1
fi

PY_MINOR=$($PYTHON -c 'import sys; print(sys.version_info.minor)')
PY_MAJOR=$($PYTHON -c 'import sys; print(sys.version_info.major)')
if [ "$PY_MAJOR" -lt 3 ] || [ "$PY_MINOR" -lt 9 ]; then
  echo -e "${RED}Python 3.9+ required. Found: $($PYTHON --version)${RESET}"
  exit 1
fi
echo -e "  Python:   ${CYAN}$($PYTHON --version)${RESET}"

# ── Clone or update repo ──────────────────────────────────────────────────────
if [ -d "$INSTALL_DIR/.git" ]; then
  echo -e "  Updating existing install…"
  git -C "$INSTALL_DIR" pull --quiet
else
  echo -e "  Cloning KPrompter…"
  git clone --quiet "$REPO" "$INSTALL_DIR"
fi

# ── Virtual environment ───────────────────────────────────────────────────────
echo -e "  Creating virtual environment…"
$PYTHON -m venv "$INSTALL_DIR/.venv"
source "$INSTALL_DIR/.venv/bin/activate"

echo -e "  Installing Python dependencies…"
pip install --quiet --upgrade pip
pip install --quiet -r "$INSTALL_DIR/requirements.txt"

# ── Platform-specific extras ──────────────────────────────────────────────────
if [ "$PLATFORM" = "macOS" ]; then
  pip install --quiet pyobjc-framework-Quartz pyobjc-framework-Cocoa 2>/dev/null || true
  # Strip Gatekeeper quarantine flag from any bundled .app
  find "$INSTALL_DIR" -name "*.app" -exec xattr -cr {} \; 2>/dev/null || true
fi

# ── Create launcher script ────────────────────────────────────────────────────
mkdir -p "$HOME/.local/bin"
cat > "$BIN_LINK" << LAUNCHEREOF
#!/usr/bin/env bash
source "$INSTALL_DIR/.venv/bin/activate"
exec python "$INSTALL_DIR/main.py" "\$@"
LAUNCHEREOF
chmod +x "$BIN_LINK"

# ── PATH hint ─────────────────────────────────────────────────────────────────
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
  echo ""
  echo -e "  ${YELLOW}Add this to your shell profile (~/.zshrc or ~/.bashrc):${RESET}"
  echo -e "  ${CYAN}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
  echo -e "  ${DIM}Then restart your terminal or run: source ~/.zshrc${RESET}"
fi

# ── Linux: desktop entry + autostart hint ────────────────────────────────────
if [ "$PLATFORM" = "Linux" ]; then
  DESKTOP_DIR="$HOME/.local/share/applications"
  mkdir -p "$DESKTOP_DIR"
  ICON_PATH="$INSTALL_DIR/assets/icon.png"
  cat > "$DESKTOP_DIR/kprompter.desktop" << DESKTOPEOF
[Desktop Entry]
Type=Application
Name=KPrompter
Comment=AI prompt optimizer — one hotkey, any app
Exec=$BIN_LINK
Icon=$ICON_PATH
Terminal=false
Categories=Utility;
StartupNotify=false
DESKTOPEOF
  echo -e "  Desktop entry: ${DIM}$DESKTOP_DIR/kprompter.desktop${RESET}"

  # Autostart
  mkdir -p "$HOME/.config/autostart"
  cp "$DESKTOP_DIR/kprompter.desktop" "$HOME/.config/autostart/kprompter.desktop"
  echo -e "  Autostart:     ${DIM}enabled${RESET}"

  echo ""
  echo -e "  ${YELLOW}Linux hotkey note:${RESET}"
  echo -e "  ${DIM}pynput needs access to /dev/input. If the hotkey doesn't fire, run:${RESET}"
  echo -e "  ${CYAN}sudo usermod -aG input \$USER${RESET}"
  echo -e "  ${DIM}Then log out and back in.${RESET}"
fi

# ── macOS: Accessibility + Login Item hint ────────────────────────────────────
if [ "$PLATFORM" = "macOS" ]; then
  echo ""
  echo -e "  ${YELLOW}macOS setup required:${RESET}"
  echo -e "  ${DIM}1. System Settings → Privacy & Security → Accessibility${RESET}"
  echo -e "  ${DIM}   Add Terminal (or KPrompter.app) to allow global hotkeys${RESET}"
  echo -e "  ${DIM}2. System Settings → General → Login Items → Add KPrompter${RESET}"
fi

echo ""
echo -e "${GREEN}${BOLD}  KPrompter installed successfully.${RESET}"
echo -e "  Run: ${CYAN}kprompter${RESET}"
echo ""
