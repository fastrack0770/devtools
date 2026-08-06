#!/bin/bash
# Run the extension's unit tests. Needs gjs (package: gjs).
#   gnome-extension/ai-usage@ai-usage-control/tests/run.sh
set -euo pipefail

EXT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v gjs >/dev/null 2>&1; then
    echo "gjs is required to run these tests: sudo apt install gjs" >&2
    exit 1
fi

# -I EXT_DIR makes imports.lib.* resolve; -I tests/stubs supplies the
# imports.misc.extensionUtils that only exists inside GNOME Shell.
exec gjs -I "$EXT_DIR" -I "$EXT_DIR/tests/stubs" "$EXT_DIR/tests/run.js"
