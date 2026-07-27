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
    # On a fresh install GNOME Shell has not scanned the new extension yet, so
    # `gnome-extensions enable` fails. Add the UUID to the gsettings key the
    # shell reads at session start instead — the extension then activates
    # automatically after the next login, no second install needed.
    gsettings set org.gnome.shell enabled-extensions "$(
        gsettings get org.gnome.shell enabled-extensions | python3 -c "
import sys, ast
raw = sys.stdin.read().strip()
lst = [] if raw in ('', '@as []') else list(ast.literal_eval(raw))
uuid = '$UUID'
if uuid not in lst:
    lst.append(uuid)
print(lst)
")"
    echo "Extension registered as enabled."
fi

echo
echo "IMPORTANT (Wayland): GNOME Shell only picks up a new extension after you"
echo "log out and log back in. It will be active right after that login."
