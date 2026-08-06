#!/bin/bash
# Take bash/bin back off your PATH — the inverse of deploy/bash-scripts.sh.
# Usage: deploy/bash-scripts-uninstall.sh
#
# Removes from your shell rc (~/.bashrc or ~/.zshrc):
#   - the '# devtools bash/bin scripts' comment line
#   - any PATH line mentioning this repo's bash/bin
#   - the blank line the installer put in front of the block
#
# The rc is backed up next to itself before it is rewritten. Idempotent: with
# nothing to remove it leaves the file alone. The scripts themselves stay in the
# repo — this only unhooks them from your shell.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="$REPO_ROOT/bash/bin"

case "${SHELL:-}" in
    */zsh) RC="$HOME/.zshrc" ;;
    *)     RC="$HOME/.bashrc" ;;
esac

if [ ! -f "$RC" ]; then
    echo "$RC does not exist — nothing to do."
    exit 0
fi

if ! grep -qF "$BIN_DIR" "$RC"; then
    echo "$BIN_DIR is not referenced in $RC — nothing to do."
    exit 0
fi

BACKUP="$RC.devtools.bak"
cp -p "$RC" "$BACKUP"

TMP="$(mktemp)"
# Blank lines are held back so the one the installer wrote above the block can be
# dropped along with it; any others are printed once a kept line shows up.
awk -v bin="$BIN_DIR" '
function flush(  i) { for (i = 1; i <= blanks; i++) print ""; blanks = 0 }
{
    if ($0 == "") { blanks++; next }
    if ($0 == "# devtools bash/bin scripts" || (index($0, bin) && index($0, "PATH"))) {
        if (blanks > 0) blanks--
        removed++
        next
    }
    flush()
    print
}
END { flush(); if (removed) printf "%d\n", removed > "/dev/stderr" }
' "$RC" > "$TMP" 2> "$TMP.count"

REMOVED="$(cat "$TMP.count" 2>/dev/null || echo 0)"
rm -f "$TMP.count"

if [ "${REMOVED:-0}" -eq 0 ]; then
    rm -f "$TMP" "$BACKUP"
    echo "Found no PATH entry for $BIN_DIR in $RC — nothing to do."
    exit 0
fi

cat "$TMP" > "$RC"
rm -f "$TMP"

echo "Removed $REMOVED line(s) for $BIN_DIR from $RC (backup: $BACKUP)"

if grep -qF "$BIN_DIR" "$RC"; then
    echo
    echo "Note: $RC still mentions $BIN_DIR on non-PATH lines — left untouched:"
    grep -nF "$BIN_DIR" "$RC" | sed 's/^/      /'
fi

echo "Open a new terminal (or re-source $RC) — the current shell keeps the old PATH."
