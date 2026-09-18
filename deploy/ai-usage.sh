#!/bin/bash
# Install the shared AI usage runtime for the current user.
# Usage: deploy/ai-usage.sh
#
# Installs to ~/.local/libexec/ai-usage-control/, whose `ai-usage` executable is
# the stable path both clients call: the GNOME Shell extension and the Godot
# Shell. It lives outside the extension's own directory on purpose — a UUID and
# an extension's internal layout are not an interface another application can
# rely on, and removing the extension must not take the Shell's data source with
# it. See the godot-mvp change `add-contextual-ai-usage-hud`, design.md D1.
#
# The swap is atomic: the new tree is written under a fresh name and a symlink
# is renamed onto it, so a shell polling once a minute never catches a half
# written runtime. Callers may point elsewhere with AI_USAGE_BIN.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO_ROOT/ai-usage"

PREFIX="${AI_USAGE_PREFIX:-$HOME/.local/libexec/ai-usage-control}"
LAUNCHER="$PREFIX/ai-usage"

if [ ! -d "$SRC/ai_usage" ]; then
    echo "Error: '$SRC/ai_usage' not found" >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is required but was not found in PATH." >&2
    exit 1
fi

STAMP="$(date +%Y%m%d%H%M%S)-$$"
NEW="$PREFIX/runtime-$STAMP"

mkdir -p "$PREFIX"
chmod 700 "$PREFIX"

# --- stage the new tree -------------------------------------------------
mkdir -p "$NEW"
cp -r "$SRC/ai_usage" "$NEW/"
find "$NEW" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
chmod +x "$NEW/ai_usage/helpers/"*.py

# --- swap the runtime symlink atomically --------------------------------
# `ln -sfn` on an existing symlink is a remove-then-create, which leaves a
# window with no runtime at all; renaming one symlink over another is a single
# rename(2) and has no such window.
ln -sfn "runtime-$STAMP" "$PREFIX/.runtime.next"
mv -T "$PREFIX/.runtime.next" "$PREFIX/runtime"

# --- then the launcher, also by rename ----------------------------------
cat > "$PREFIX/.ai-usage.next" <<'LAUNCHER_EOF'
#!/bin/bash
# The shared AI usage runtime. Prints one schema-v1 JSON document on stdout.
#   ai-usage            use the 60-second cache when it is fresh
#   ai-usage --force    skip the freshness window (a manual refresh)
# Installed by devtools/deploy/ai-usage.sh; do not edit in place.
set -euo pipefail
ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
exec env PYTHONPATH="$ROOT/runtime${PYTHONPATH:+:$PYTHONPATH}" python3 -m ai_usage "$@"
LAUNCHER_EOF
chmod 755 "$PREFIX/.ai-usage.next"
mv -f "$PREFIX/.ai-usage.next" "$LAUNCHER"

# --- drop the trees no symlink points at any more ------------------------
CURRENT="$(readlink "$PREFIX/runtime")"
for old in "$PREFIX"/runtime-*; do
    [ -d "$old" ] || continue
    [ "$(basename "$old")" = "$CURRENT" ] && continue
    rm -rf "$old"
done

echo "Installed the shared usage runtime to $LAUNCHER"

# Proof it runs at all, before either client is told to depend on it. A failure
# here is a broken install, not a logged-out CLI: a CLI that is not set up is
# reported inside the document as an unavailable provider.
if ! "$LAUNCHER" >/dev/null 2>&1; then
    echo "Warning: $LAUNCHER did not run cleanly — check: $LAUNCHER" >&2
fi
