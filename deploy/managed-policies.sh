#!/bin/bash
# Install the managed policy files for Claude Code and Codex system-wide.
# Usage: deploy/managed-policies.sh
#
# Mirrors this repo's etc/ tree onto the system:
#   etc/claude-code/managed-settings.json -> /etc/claude-code/managed-settings.json
#   etc/claude-code/managed-mcp.json      -> /etc/claude-code/managed-mcp.json
#   etc/codex/requirements.toml           -> /etc/codex/requirements.toml
#
# The repo copies are templates: the @CODEX_BIN@ placeholder is replaced with
# the codex binary found via `command -v codex` at install time (managed-mcp.json
# and allowedMcpServers in managed-settings.json must agree on it exactly).
#
# Writing under /etc needs root, so each copy goes through sudo (skipped when
# already running as root). Idempotent: files whose installed content already
# matches the rendered templates are left untouched.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO_ROOT/etc"

FILES=(
    claude-code/managed-settings.json
    claude-code/managed-mcp.json
    codex/requirements.toml
)

CODEX_BIN="$(command -v codex || true)"
if [ -z "$CODEX_BIN" ]; then
    echo "Error: codex was not found on PATH — the managed policies must point" >&2
    echo "       at a real binary. Install codex first." >&2
    exit 1
fi
echo "Using codex at $CODEX_BIN"

SUDO="sudo"
if [ "$(id -u)" -eq 0 ]; then
    SUDO=""
fi

RENDER_DIR="$(mktemp -d)"
trap 'rm -rf "$RENDER_DIR"' EXIT

for rel in "${FILES[@]}"; do
    src="$SRC/$rel"
    dst="/etc/$rel"
    if [ ! -f "$src" ]; then
        echo "Error: $src is missing" >&2
        exit 1
    fi
    rendered="$RENDER_DIR/${rel//\//_}"
    sed "s|@CODEX_BIN@|$CODEX_BIN|g" "$src" > "$rendered"
    if [ -f "$dst" ] && cmp -s "$rendered" "$dst"; then
        echo "$dst is already up to date."
        continue
    fi
    $SUDO install -D -m 0644 -o root -g root "$rendered" "$dst"
    echo "Installed $dst"
done

# The repo copies ship with a placeholder for the machine-private path.
if grep -rqs "ABSOLUTE/PRIVATE/PATH" "$SRC"; then
    echo "Note: the /ABSOLUTE/PRIVATE/PATH placeholder is still present in the" >&2
    echo "      policy files — replace it with a real path (or drop those entries)." >&2
fi

echo "Done. Claude Code and Codex pick the policies up on their next start."
