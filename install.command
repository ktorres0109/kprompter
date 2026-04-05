#!/bin/bash
# KPrompter installer — strips Gatekeeper quarantine and moves to /Applications
APP="$(dirname "$0")/KPrompter.app"
if [ ! -d "$APP" ]; then
  echo "KPrompter.app not found next to this script."
  exit 1
fi
echo "Installing KPrompter..."
xattr -dr com.apple.quarantine "$APP"
rm -rf /Applications/KPrompter.app
ditto "$APP" /Applications/KPrompter.app
echo "Done! KPrompter is now in your Applications folder."
open /Applications/KPrompter.app
