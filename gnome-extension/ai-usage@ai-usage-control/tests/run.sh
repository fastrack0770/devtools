#!/bin/bash
# Run the extension's unit tests. Needs gjs (package: gjs).
#   gnome-extension/ai-usage@ai-usage-control/tests/run.sh
set -euo pipefail

EXT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v gjs >/dev/null 2>&1; then
    echo "gjs is required to run these tests: sudo apt install gjs" >&2
    exit 1
fi

# -I EXT_DIR makes imports.aiusagelib.* resolve, which is the same route both
# entry points use inside a live shell — so nothing under test needs a stub.
exec gjs -I "$EXT_DIR" "$EXT_DIR/tests/run.js" "$EXT_DIR"
