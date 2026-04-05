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
  *)      echo -e "${RED}Unsupported OS: $OS${RESET}"; exit 1 ;;
esac
echo -e "  Platform: ${CYAN}$PLATFORM${RESET}"

# ── Check Python ─────────────────────────────────────────────────────────────
if command -v python3 &>/dev/null; then
  PYTHON=python3
elif command -v python &>/dev/null; then
  PYTHON=python
else
  echo -e "${RED}Python 3 not found. Please install Python 3.9+.${RESET}"
  exit 1
fi

PY_VERSION=$($PYTHON -c 'import sys; print(sys.version_info.minor)')
if [ "$PY_VERSION" -lt 9 ]; then
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

echo -e "  Installing dependencies…"
pip install --quiet --upgrade pip
pip install --quiet -r "$INSTALL_DIR/requirements.txt"

# macOS extra
if [ "$PLATFORM" = "macOS" ]; then
  pip install --quiet pyobjc-framework-Quartz pyobjc-framework-Cocoa 2>/dev/null || true

# Strip macOS Gatekeeper quarantine so the app opens without "unidentified developer" prompt
  find "$INSTALL_DIR" -name "*.app" -exec xattr -cr {} \; 2>/dev/null || true

  echo ""
  echo -e "  ${CYAN}macOS Accessibility permission required${RESET}"
  echo -e "  ${DIM}Go to: System Settings → Privacy & Security → Accessibility${RESET}"
  echo -e "  ${DIM}Add Terminal (or KPrompter) to allow the hotkey to work.${RESET}"

fi

# ── Create launcher script ───────────────────────────────────────────────────
mkdir -p "$HOME/.local/bin"
cat > "$BIN_LINK" <<EOF
#!/usr/bin/env bash
source "$INSTALL_DIR/.venv/bin/activate"
exec python "$INSTALL_DIR/main.py" "\$@"
EOF
chmod +x "$BIN_LINK"

# ── Add to PATH hint ─────────────────────────────────────────────────────────
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
  echo ""
  echo -e "  ${DIM}Add this to your shell profile (~/.zshrc or ~/.bashrc):${RESET}"
  echo -e "  ${CYAN}export PATH=\"\$HOME/.local/bin:\$PATH\"${RESET}"
fi

# ── macOS: add Login Item hint ───────────────────────────────────────────────
if [ "$PLATFORM" = "macOS" ]; then
  echo ""
  echo -e "  ${DIM}To start KPrompter on login, add it to System Settings → General → Login Items.${RESET}"
fi

# ── Linux: create .desktop entry ─────────────────────────────────────────────
if [ "$PLATFORM" = "Linux" ]; then
  DESKTOP_DIR="$HOME/.local/share/applications"
  mkdir -p "$DESKTOP_DIR"
  ICON_PATH="$INSTALL_DIR/assets/icon.png"
  cat > "$DESKTOP_DIR/kprompter.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=KPrompter
Comment=AI prompt optimizer
Exec=$BIN_LINK
Icon=$ICON_PATH
Terminal=false
Categories=Utility;
StartupNotify=false
EOF
  echo -e "  Desktop entry created at ${DIM}$DESKTOP_DIR/kprompter.desktop${RESET}"
fi

echo ""
echo -e "${GREEN}${BOLD}  KPrompter installed.${RESET}"
echo -e "  Run: ${CYAN}kprompter${RESET}"
echo ""
