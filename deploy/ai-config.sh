#!/bin/bash
# Deploy the coding-agent base config (Claude Code + Codex) into a project.
# Usage: deploy/ai-config.sh <project-dir>
#
# Copies the portable parts of this repo into <project-dir>:
#   - .claude/skills/           (promoted skills + nested scripts/references/templates)
#   - .claude/commands/         (opsx slash commands, if present in this repo)
#   - .claude/opsx/             (provider-neutral opsx docs the explore skills point at)
#   - .claude/settings.json     (hook wiring; uses CLAUDE_PROJECT_DIR, so it's portable)
#   - .codex/skills/            (adapted openspec workflow + promoted methodology skills)
#   - scripts/hooks/*.py        (skill-routing hooks)
#   - CLAUDE.md                 (working rules, in a marker-delimited managed block)
#   - AGENTS.md                 (the Codex-side rules, same mechanics)
#
# Re-running this is the way to pull skill updates into a project, so every step is
# idempotent: the rules live between BEGIN/END markers and get replaced in place
# rather than prepended again. A block written by an older version of this script
# (no markers, or the pre-rename claude-config.sh marker) is migrated on the next run.
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

mkdir -p "$DEST/.claude/skills" "$DEST/.codex/skills" "$DEST/scripts/hooks"

MANIFEST="$REPO_ROOT/.claude/skill-manifest.json"
mapfile -t PROMOTED_SKILLS < <(python3 -c \
    'import json,sys; print(*json.load(open(sys.argv[1]))["promoted"], sep="\n")' "$MANIFEST")
mapfile -t IN_PROGRESS_SKILLS < <(python3 -c \
    'import json,sys; print(*json.load(open(sys.argv[1]))["in_progress"], sep="\n")' "$MANIFEST")

# Copy only promoted Claude skills, including nested scripts/references/templates.
for skill in "${PROMOTED_SKILLS[@]}"; do
    rm -rf "$DEST/.claude/skills/$skill"
    cp -r "$REPO_ROOT/.claude/skills/$skill" "$DEST/.claude/skills/$skill"
done
for skill in "${IN_PROGRESS_SKILLS[@]}"; do
    rm -rf "$DEST/.claude/skills/$skill"
done
echo "Skipped in-progress skills: ${IN_PROGRESS_SKILLS[*]:-(none)}"

# Codex loads project skills from .codex/skills. It gets its own copy of the openspec
# workflow — same steps, wired to Codex's tools — so the two trees are not interchangeable.
cp -r "$REPO_ROOT/.codex/skills/." "$DEST/.codex/skills/"

# Give Codex the promoted methodology set too. Keep its existing openspec-* copies:
# those are adapted to Codex and must not be overwritten by Claude variants. Exclude
# parallel-dev because it orchestrates Claude-side tooling, and exclude frontmatter
# disable-model-invocation skills because Codex must not invoke human-only commands.
for skill in "${PROMOTED_SKILLS[@]}"; do
    case "$skill" in
        openspec-*|parallel-dev) continue ;;
    esac
    if grep -q '^disable-model-invocation: true$' "$REPO_ROOT/.claude/skills/$skill/SKILL.md"; then
        rm -rf "$DEST/.codex/skills/$skill"
        continue
    fi
    rm -rf "$DEST/.codex/skills/$skill"
    cp -r "$REPO_ROOT/.claude/skills/$skill" "$DEST/.codex/skills/$skill"
done
rm -rf "$DEST/.codex/skills/parallel-dev"
for skill in "${IN_PROGRESS_SKILLS[@]}"; do
    rm -rf "$DEST/.codex/skills/$skill"
done

# opsx slash commands — optional: this repo only carries them when openspec init
# has been run here. The target can regenerate them with its own openspec init.
if [ -d "$REPO_ROOT/.claude/commands" ]; then
    mkdir -p "$DEST/.claude/commands"
    cp -r "$REPO_ROOT/.claude/commands/." "$DEST/.claude/commands/"
fi

# Shared opsx docs (ideation lenses, refinement rubric). Both explore skills point at
# these paths, so they ship even when only the Codex side is used.
if [ -d "$REPO_ROOT/.claude/opsx" ]; then
    mkdir -p "$DEST/.claude/opsx"
    cp -r "$REPO_ROOT/.claude/opsx/." "$DEST/.claude/opsx/"
fi

# Skill-routing hooks.
cp "$REPO_ROOT/scripts/hooks/"*.py "$DEST/scripts/hooks/"

# Drop any Python bytecode that rode along in the copies.
find "$DEST/.claude/skills" "$DEST/.codex/skills" "$DEST/scripts/hooks" \
    \( -name '__pycache__' -type d -prune -exec rm -rf {} + \) -o \
    \( -name '*.pyc' -exec rm -f {} + \)

# Restore executable bits on skill scripts (cp may drop them under some umasks).
find "$DEST/.claude/skills" "$DEST/.codex/skills" -type f \( -name '*.sh' -o -name '*.py' \) \
    -path '*/scripts/*' -exec chmod +x {} +

if [ -f "$DEST/.claude/settings.json" ]; then
    echo "Note: $DEST/.claude/settings.json already exists — left untouched."
    echo "      Merge the 'hooks' block from $REPO_ROOT/.claude/settings.json manually."
else
    cp "$REPO_ROOT/.claude/settings.json" "$DEST/.claude/settings.json"
fi

# Rules files, kept in marker-delimited managed blocks so re-runs update them in place.
#
#   deploy_rules <source-md> <dest-md> <label> <begin-mark> <end-mark> [old-begin-mark]
#
# <label> is what the messages call the block. <old-begin-mark> is an opening line an
# earlier version of this script wrote: it is matched as well and rewritten to the
# current one, otherwise the block would read as unmanaged text and a second copy
# would land on top of it.
deploy_rules() {
    local src="$1" dest_md="$2" label="$3" begin_mark="$4" end_mark="$5" old_begin_mark="${6-}"
    local block new_md match_begin ref_bytes stale

    [ -f "$src" ] || return 0

    block="$(mktemp)"
    new_md="$(mktemp)"
    { printf '%s\n' "$begin_mark"; cat "$src"; printf '%s\n' "$end_mark"; } > "$block"

    # Which opening marker this project carries, if any — current or pre-rename.
    match_begin=""
    if [ -f "$dest_md" ] && grep -qF "$end_mark" "$dest_md"; then
        if grep -qF "$begin_mark" "$dest_md"; then
            match_begin="$begin_mark"
        elif [ -n "$old_begin_mark" ] && grep -qF "$old_begin_mark" "$dest_md"; then
            match_begin="$old_begin_mark"
        fi
    fi

    if [ ! -f "$dest_md" ]; then
        cp "$block" "$dest_md"
        echo "Wrote $label to $dest_md"

    elif [ -n "$match_begin" ]; then
        # Managed block already there — swap its contents, leave the rest alone.
        awk -v b="$match_begin" -v e="$end_mark" -v block="$block" '
            index($0, b) { while ((getline l < block) > 0) print l; close(block); drop = 1; next }
            drop && index($0, e) { drop = 0; next }
            drop { next }
            { print }
        ' "$dest_md" > "$new_md"
        if cmp -s "$dest_md" "$new_md"; then
            echo "The $label in $dest_md is already up to date."
        else
            cat "$new_md" > "$dest_md"
            if [ "$match_begin" != "$begin_mark" ]; then
                echo "Updated the $label in $dest_md (marker migrated from claude-config.sh)."
            else
                echo "Updated the $label in $dest_md"
            fi
        fi

    else
        # Pre-marker layout: older runs prepended the rules verbatim, once per run.
        # Peel off however many copies are stacked at the top, then write the block.
        cat "$dest_md" > "$new_md"
        ref_bytes="$(wc -c < "$src")"
        stale=0
        while [ "$(wc -c < "$new_md")" -ge "$ref_bytes" ] \
            && head -c "$ref_bytes" "$new_md" | cmp -s - "$src"; do
            # Drop the copy, then the blank line the old script put after it.
            tail -c "+$((ref_bytes + 1))" "$new_md" \
                | awk 'NR == 1 && $0 == "" { next } { print }' > "$new_md.trim"
            mv "$new_md.trim" "$new_md"
            stale=$((stale + 1))
        done

        { cat "$block"; printf '\n'; cat "$new_md"; } > "$new_md.out"
        mv "$new_md.out" "$dest_md"

        if [ "$stale" -gt 0 ]; then
            echo "Note: replaced $stale unmarked copy/copies of the $label at the top of $dest_md."
        else
            echo "Note: prepended the $label to existing $dest_md."
        fi
    fi

    rm -f "$block" "$new_md"
}

# Claude Code reads CLAUDE.md; Codex reads AGENTS.md and never sees the former, so it
# gets its own block — the Claude rules lean on hooks that do not fire in a Codex
# session, and repeating them verbatim there would be wrong.
deploy_rules "$REPO_ROOT/CLAUDE.md" "$DEST/CLAUDE.md" "base-rules block" \
    '<!-- BEGIN devtools base rules — managed by deploy/ai-config.sh -->' \
    '<!-- END devtools base rules -->' \
    '<!-- BEGIN devtools base rules — managed by deploy/claude-config.sh -->'

deploy_rules "$REPO_ROOT/.codex/AGENTS.md" "$DEST/AGENTS.md" "codex-rules block" \
    '<!-- BEGIN devtools codex rules — managed by deploy/ai-config.sh -->' \
    '<!-- END devtools codex rules -->'

echo "Coding-agent base config deployed to $DEST (.claude + .codex)"
