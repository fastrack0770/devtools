#!/bin/bash
# Deploy the Claude Code base config into a project.
# Usage: deploy/claude-config.sh <project-dir>
#
# Copies the portable parts of this repo into <project-dir>:
#   - .claude/skills/           (skills + their nested scripts/, references/, templates/)
#   - .claude/commands/         (opsx slash commands)
#   - .claude/settings.json     (hook wiring; uses CLAUDE_PROJECT_DIR, so it's portable)
#   - scripts/hooks/*.py        (skill-routing hooks)
#   - CLAUDE.md                 (working rules; prepended if the project already has one)
#
# settings.local.json is intentionally NOT copied (machine/project-specific).
# __pycache__/*.pyc are stripped from the destination.
# Executable bits on skill scripts are restored after the copy.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ $# -ne 1 ]; then
    echo "Usage: $0 <project-dir>" >&2
    exit 1
fi

DEST="$1"
if [ ! -d "$DEST" ]; then
    echo "Error: '$DEST' is not a directory" >&2
    exit 1
fi

mkdir -p "$DEST/.claude/skills" "$DEST/.claude/commands" "$DEST/scripts/hooks"

# Skills, including each skill's nested scripts/, references/ and templates/.
cp -r "$REPO_ROOT/.claude/skills/." "$DEST/.claude/skills/"

# opsx slash commands (openspec init can still regenerate these in the target).
cp -r "$REPO_ROOT/.claude/commands/." "$DEST/.claude/commands/"

# Skill-routing hooks.
cp "$REPO_ROOT/scripts/hooks/"*.py "$DEST/scripts/hooks/"

# Drop any Python bytecode that rode along in the copies.
find "$DEST/.claude/skills" "$DEST/scripts/hooks" \
    \( -name '__pycache__' -type d -prune -exec rm -rf {} + \) -o \
    \( -name '*.pyc' -exec rm -f {} + \)

# Restore executable bits on skill scripts (cp may drop them under some umasks).
find "$DEST/.claude/skills" -type f \( -name '*.sh' -o -name '*.py' \) \
    -path '*/scripts/*' -exec chmod +x {} +

if [ -f "$DEST/.claude/settings.json" ]; then
    echo "Note: $DEST/.claude/settings.json already exists — left untouched."
    echo "      Merge the 'hooks' block from $REPO_ROOT/.claude/settings.json manually."
else
    cp "$REPO_ROOT/.claude/settings.json" "$DEST/.claude/settings.json"
fi

# CLAUDE.md working rules.
#   - If the project already has a CLAUDE.md, prepend ours to the beginning of it.
#   - Otherwise, just copy it.
if [ -f "$REPO_ROOT/CLAUDE.md" ]; then
    if [ -f "$DEST/CLAUDE.md" ]; then
        TMP_CLAUDE="$(mktemp)"
        cat "$REPO_ROOT/CLAUDE.md" > "$TMP_CLAUDE"
        printf '\n' >> "$TMP_CLAUDE"
        cat "$DEST/CLAUDE.md" >> "$TMP_CLAUDE"
        mv "$TMP_CLAUDE" "$DEST/CLAUDE.md"
        echo "Note: prepended base rules to existing $DEST/CLAUDE.md."
    else
        cp "$REPO_ROOT/CLAUDE.md" "$DEST/CLAUDE.md"
    fi
fi

echo "Claude Code base config deployed to $DEST"
