#!/bin/bash
# Install the AI Usage GNOME Shell extension for the current user.
# Usage: deploy/gnome-extension.sh
#
# Copies gnome-extension/ai-usage@ai-usage-control into
# ~/.local/share/gnome-shell/extensions/ and enables it.
# Idempotent: running it twice just overwrites the installed copy.
#
# The extension used to ship under the UUID claude-usage@claude-usage-control.
# A UUID is the install identity, so the renamed package installs alongside
# the old one instead of replacing it — hence the removal step below, without
# which the panel would show two Claude bars.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

UUID="ai-usage@ai-usage-control"
OLD_UUID="claude-usage@claude-usage-control"
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

# Rewrite the gsettings list of enabled extensions: drop $1, add $2 (either
# may be empty). GNOME stores it as a GVariant array literal, so it is parsed
# and re-emitted with python rather than patched textually.
update_enabled() {
    local remove="$1" add="$2" current
    current="$(gsettings get org.gnome.shell enabled-extensions)"
    gsettings set org.gnome.shell enabled-extensions "$(
        REMOVE="$remove" ADD="$add" python3 -c "
import ast, os, sys
raw = sys.stdin.read().strip()
lst = [] if raw in ('', '@as []') else list(ast.literal_eval(raw))
remove, add = os.environ['REMOVE'], os.environ['ADD']
if remove:
    lst = [u for u in lst if u != remove]
if add and add not in lst:
    lst.append(add)
print(lst)
" <<<"$current")"
}

# --- retire the pre-rename install -------------------------------------
OLD_DEST="$HOME/.local/share/gnome-shell/extensions/$OLD_UUID"
if [ -d "$OLD_DEST" ]; then
    gnome-extensions disable "$OLD_UUID" 2>/dev/null || true
    rm -rf "$OLD_DEST"
    update_enabled "$OLD_UUID" "" 2>/dev/null || true
    echo "Removed the previous install ($OLD_UUID)."
fi

mkdir -p "$DEST/lib"
cp -f "$SRC"/metadata.json "$SRC"/extension.js "$SRC"/stylesheet.css "$DEST"/
cp -f "$SRC"/lib/*.js "$DEST/lib/"
cp -f "$SRC"/claude-usage-helper.py "$SRC"/codex-usage-helper.py "$DEST"/
chmod +x "$DEST/claude-usage-helper.py" "$DEST/codex-usage-helper.py"

echo "Installed to $DEST"

if gnome-extensions enable "$UUID" 2>/dev/null; then
    echo "Extension enabled."
else
    # On a fresh install GNOME Shell has not scanned the new extension yet, so
    # `gnome-extensions enable` fails. Add the UUID to the gsettings key the
    # shell reads at session start instead — the extension then activates
    # automatically after the next login, no second install needed.
    update_enabled "" "$UUID"
    echo "Extension registered as enabled."
fi

echo
echo "IMPORTANT (Wayland): GNOME Shell only picks up a new extension after you"
echo "log out and log back in. It will be active right after that login."

# A provider's bar only appears when that CLI is logged in, so an install
# with neither one present shows an empty panel. Say so here rather than
# leaving the user wondering.
CLAUDE_CREDS="$HOME/.claude/.credentials.json"
CODEX_AUTH="$HOME/.codex/auth.json"
have_any=0
[ -f "$CLAUDE_CREDS" ] && have_any=1
[ -f "$CODEX_AUTH" ] && have_any=1

if [ "$have_any" -eq 0 ]; then
    echo
    echo "WARNING: neither CLI is logged in, so no bar will appear yet."
    echo "  Claude Code:  curl -fsSL https://claude.ai/install.sh | bash"
    echo "                claude          # then run /login inside the CLI"
    echo "  Codex:        npm i -g @openai/codex"
    echo "                codex login"
    echo "Each bar shows up on its own within a minute of logging in."
else
    [ -f "$CLAUDE_CREDS" ] || echo "Note: Claude Code is not logged in — only the Codex bar will show."
    [ -f "$CODEX_AUTH" ] || echo "Note: Codex is not logged in — only the Claude bar will show."
fi
