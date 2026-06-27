#!/bin/bash
# Make the scripts in bash/bin available as commands in your terminal.
# Usage: deploy/bash-scripts.sh
#
# Appends bash/bin to PATH in your shell rc (~/.bashrc or ~/.zshrc).
# Idempotent: running it twice does not duplicate the entry.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="$REPO_ROOT/bash/bin"

case "${SHELL:-}" in
    */zsh) RC="$HOME/.zshrc" ;;
    *)     RC="$HOME/.bashrc" ;;
esac

LINE="export PATH=\"$BIN_DIR:\$PATH\"  # devtools bash/bin"

# Make the scripts executable in case the file modes were lost.
chmod +x "$BIN_DIR"/* 2>/dev/null || true

if [ -f "$RC" ] && grep -qF "$BIN_DIR" "$RC"; then
    echo "$BIN_DIR is already on PATH via $RC — nothing to do."
else
    printf '\n# devtools bash/bin scripts\n%s\n' "$LINE" >> "$RC"
    echo "Added $BIN_DIR to PATH in $RC"
fi

echo "Run 'source $RC' or open a new terminal to pick up the scripts."
