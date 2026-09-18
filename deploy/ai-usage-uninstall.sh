#!/bin/bash
# Remove the shared AI usage runtime.
# Usage: deploy/ai-usage-uninstall.sh
#
# Separate from the extension's uninstall on purpose: the Godot Shell reads this
# runtime too, so `make uninstall gnome-extension` leaves it alone and taking it
# away is an explicit act (design.md D1). The cache it wrote holds no secrets and
# is removed with it.
set -euo pipefail

PREFIX="${AI_USAGE_PREFIX:-$HOME/.local/libexec/ai-usage-control}"
CACHE="${AI_USAGE_CACHE_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/ai-usage-control}"

rm -rf "$PREFIX"
rm -rf "$CACHE"

echo "Removed $PREFIX and its cache."
echo "Note: any client still configured to call it — the GNOME extension, the"
echo "      Godot Shell — will now report usage as unavailable rather than fail."
