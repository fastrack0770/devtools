#!/bin/bash
# Deploy the Claude Code base config into a project.
# Usage: deploy/claude-config.sh <project-dir>
#
# Copies the portable parts of this repo into <project-dir>:
#   - .claude/skills/           (skills + their nested scripts/, references/, templates/)
#   - .claude/commands/         (opsx slash commands, if present in this repo)
#   - .claude/settings.json     (hook wiring; uses CLAUDE_PROJECT_DIR, so it's portable)
#   - scripts/hooks/*.py        (skill-routing hooks)
#   - CLAUDE.md                 (working rules, in a marker-delimited managed block)
#
# Re-running this is the way to pull skill updates into a project, so every step is
# idempotent: the CLAUDE.md rules live between BEGIN/END markers and get replaced in
# place rather than prepended again. A block written by an older version of this
# script (no markers) is migrated on the next run.
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

mkdir -p "$DEST/.claude/skills" "$DEST/scripts/hooks"

# Skills, including each skill's nested scripts/, references/ and templates/.
cp -r "$REPO_ROOT/.claude/skills/." "$DEST/.claude/skills/"

# opsx slash commands — optional: this repo only carries them when openspec init
# has been run here. The target can regenerate them with its own openspec init.
if [ -d "$REPO_ROOT/.claude/commands" ]; then
    mkdir -p "$DEST/.claude/commands"
    cp -r "$REPO_ROOT/.claude/commands/." "$DEST/.claude/commands/"
fi

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

# CLAUDE.md working rules, kept in a managed block so re-runs update it in place.
BEGIN_MARK='<!-- BEGIN devtools base rules — managed by deploy/claude-config.sh -->'
END_MARK='<!-- END devtools base rules -->'

if [ -f "$REPO_ROOT/CLAUDE.md" ]; then
    DEST_MD="$DEST/CLAUDE.md"

    BLOCK="$(mktemp)"
    NEW_MD="$(mktemp)"
    trap 'rm -f "$BLOCK" "$NEW_MD"' EXIT
    { printf '%s\n' "$BEGIN_MARK"; cat "$REPO_ROOT/CLAUDE.md"; printf '%s\n' "$END_MARK"; } > "$BLOCK"

    if [ ! -f "$DEST_MD" ]; then
        cp "$BLOCK" "$DEST_MD"
        echo "Wrote base rules to $DEST_MD"

    elif grep -qF "$BEGIN_MARK" "$DEST_MD" && grep -qF "$END_MARK" "$DEST_MD"; then
        # Managed block already there — swap its contents, leave the rest alone.
        awk -v b="$BEGIN_MARK" -v e="$END_MARK" -v block="$BLOCK" '
            index($0, b) { while ((getline l < block) > 0) print l; close(block); drop = 1; next }
            drop && index($0, e) { drop = 0; next }
            drop { next }
            { print }
        ' "$DEST_MD" > "$NEW_MD"
        if cmp -s "$DEST_MD" "$NEW_MD"; then
            echo "Base rules in $DEST_MD are already up to date."
        else
            cat "$NEW_MD" > "$DEST_MD"
            echo "Updated the base-rules block in $DEST_MD"
        fi

    else
        # Pre-marker layout: older runs prepended the rules verbatim, once per run.
        # Peel off however many copies are stacked at the top, then write the block.
        cat "$DEST_MD" > "$NEW_MD"
        REF_BYTES="$(wc -c < "$REPO_ROOT/CLAUDE.md")"
        STALE=0
        while [ "$(wc -c < "$NEW_MD")" -ge "$REF_BYTES" ] \
            && head -c "$REF_BYTES" "$NEW_MD" | cmp -s - "$REPO_ROOT/CLAUDE.md"; do
            # Drop the copy, then the blank line the old script put after it.
            tail -c "+$((REF_BYTES + 1))" "$NEW_MD" \
                | awk 'NR == 1 && $0 == "" { next } { print }' > "$NEW_MD.trim"
            mv "$NEW_MD.trim" "$NEW_MD"
            STALE=$((STALE + 1))
        done

        { cat "$BLOCK"; printf '\n'; cat "$NEW_MD"; } > "$NEW_MD.out"
        mv "$NEW_MD.out" "$DEST_MD"

        if [ "$STALE" -gt 0 ]; then
            echo "Note: replaced $STALE unmarked copy/copies of the base rules at the top of $DEST_MD."
        else
            echo "Note: prepended the base-rules block to existing $DEST_MD."
        fi
    fi

    rm -f "$BLOCK" "$NEW_MD"
    trap - EXIT
fi

echo "Claude Code base config deployed to $DEST"
