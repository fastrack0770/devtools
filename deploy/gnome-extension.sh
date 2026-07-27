#!/bin/bash
# Install the Claude Usage GNOME Shell extension for the current user.
# Usage: deploy/gnome-extension.sh
#
# Copies gnome-extension/claude-usage@claude-usage-control into
# ~/.local/share/gnome-shell/extensions/ and enables it.
# Idempotent: running it twice just overwrites the installed copy.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

UUID="claude-usage@claude-usage-control"
SRC="$REPO_ROOT/gnome-extension/$UUID"
DEST="$HOME/.local/share/gnome-shell/extensions/$UUID"

if [ ! -d "$SRC" ]; then
    echo "Error: '$SRC' not found" >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required but was not found in PATH." >&2
    exit 1
fi

mkdir -p "$DEST"
cp -f "$SRC"/metadata.json "$SRC"/extension.js "$SRC"/stylesheet.css "$SRC"/usage-helper.py "$DEST"/
chmod +x "$DEST/usage-helper.py"

echo "Installed to $DEST"

if gnome-extensions enable "$UUID" 2>/dev/null; then
    echo "Extension enabled."
else
    echo "Enable it after restarting GNOME Shell:"
    echo "  gnome-extensions enable $UUID"
fi

echo
echo "IMPORTANT (Wayland): GNOME Shell only picks up a new extension after you"
echo "log out and log back in."
