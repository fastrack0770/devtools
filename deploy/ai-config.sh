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
#
# --global installs the skills into the per-user directories both agents scan in every
# project: ${CLAUDE_CONFIG_DIR:-~/.claude}/skills and ${CODEX_HOME:-~/.codex}/skills, and
# wires the skill-routing hooks (copied to ~/.claude/hooks/devtools/) into the user-level
# settings.json. The rules files stay per-project. Only the skills and hook entries this
# repo names are replaced; anything else in those places is left alone.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ $# -ne 1 ]; then
    echo "Usage: $0 <project-dir> | --global" >&2
    exit 1
fi

MANIFEST="$REPO_ROOT/.claude/skill-manifest.json"
mapfile -t PROMOTED_SKILLS < <(python3 -c \
    'import json,sys; print(*json.load(open(sys.argv[1]))["promoted"], sep="\n")' "$MANIFEST")
mapfile -t IN_PROGRESS_SKILLS < <(python3 -c \
    'import json,sys; print(*json.load(open(sys.argv[1]))["in_progress"], sep="\n")' "$MANIFEST")

# Copy only promoted Claude skills, including nested scripts/references/templates.
install_claude_skills() {
    local dir="$1" skill
    mkdir -p "$dir"
    for skill in "${PROMOTED_SKILLS[@]}"; do
        rm -rf "$dir/$skill"
        cp -r "$REPO_ROOT/.claude/skills/$skill" "$dir/$skill"
    done
    for skill in "${IN_PROGRESS_SKILLS[@]}"; do
        rm -rf "$dir/$skill"
    done
}

install_codex_skills() {
    local dir="$1" skill
    mkdir -p "$dir"

    # Codex gets its own copy of the openspec workflow — same steps, wired to Codex's
    # tools — so the two trees are not interchangeable.
    cp -r "$REPO_ROOT/.codex/skills/." "$dir/"

    # Give Codex the promoted methodology set too. Keep its existing openspec-* copies:
    # those are adapted to Codex and must not be overwritten by Claude variants. Exclude
    # parallel-dev because it orchestrates Claude-side tooling, and exclude frontmatter
    # disable-model-invocation skills because Codex must not invoke human-only commands.
    for skill in "${PROMOTED_SKILLS[@]}"; do
        case "$skill" in
            openspec-*|parallel-dev) continue ;;
        esac
        rm -rf "$dir/$skill"
        if grep -q '^disable-model-invocation: true$' "$REPO_ROOT/.claude/skills/$skill/SKILL.md"; then
            continue
        fi
        cp -r "$REPO_ROOT/.claude/skills/$skill" "$dir/$skill"
    done
    rm -rf "$dir/parallel-dev"
    for skill in "${IN_PROGRESS_SKILLS[@]}"; do
        rm -rf "$dir/$skill"
    done
}

# Drop Python bytecode that rode along in the copies, and restore executable bits on
# skill scripts (cp may drop them under some umasks).
tidy_skills() {
    find "$@" \
        \( -name '__pycache__' -type d -prune -exec rm -rf {} + \) -o \
        \( -name '*.pyc' -exec rm -f {} + \)
    find "$@" -type f \( -name '*.sh' -o -name '*.py' \) \
        -path '*/scripts/*' -exec chmod +x {} +
}

# Wire the skill-routing hooks into the user-level settings.json. Each command steps
# aside when the project's own settings.json already wires the same script, so a deployed
# project does not get every [skill-routing] line twice. Existing keys and other hooks
# are preserved; our entries are found again by their hooks/devtools/ path, which keeps
# re-runs idempotent. A settings.json that is not valid JSON is left alone.
wire_global_hooks() {
    python3 - "$1" <<'PY'
import json, os, sys

path = sys.argv[1]
WIRING = [("UserPromptSubmit", None, "skill_suggest.py"),
          ("PostToolUse", "Skill", "opsx_skill_routing.py")]

def command(script):
    return ('grep -qs %s "${CLAUDE_PROJECT_DIR:-.}/.claude/settings.json" || '
            'python3 "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/devtools/%s" '
            '2>/dev/null || true' % (script, script))

before = open(path).read() if os.path.exists(path) else ""
try:
    settings = json.loads(before) if before.strip() else {}
except ValueError as e:
    sys.exit("Error: %s is not valid JSON (%s) — hooks not wired, file left untouched." % (path, e))

hooks = settings.setdefault("hooks", {})
for event, matcher, script in WIRING:
    groups = hooks.get(event, [])
    for g in groups:
        g["hooks"] = [h for h in g.get("hooks", [])
                      if "hooks/devtools/" + script not in h.get("command", "")]
    groups = [g for g in groups if g["hooks"]]
    group = {"hooks": [{"type": "command", "command": command(script)}]}
    if matcher:
        group = {"matcher": matcher, **group}
    hooks[event] = groups + [group]

after = json.dumps(settings, indent=2, ensure_ascii=False) + "\n"
if after == before:
    print("Skill-routing hooks in %s are already up to date." % path)
else:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(after)
    os.replace(tmp, path)
    print("Wired the skill-routing hooks into %s" % path)
PY
}

if [ "$1" = "--global" ]; then
    CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
    CLAUDE_SKILLS="$CLAUDE_DIR/skills"
    CODEX_SKILLS="${CODEX_HOME:-$HOME/.codex}/skills"
    install_claude_skills "$CLAUDE_SKILLS"
    install_codex_skills "$CODEX_SKILLS"
    tidy_skills "$CLAUDE_SKILLS" "$CODEX_SKILLS"
    echo "Skipped in-progress skills: ${IN_PROGRESS_SKILLS[*]:-(none)}"
    echo "Skills installed for every project: $CLAUDE_SKILLS and $CODEX_SKILLS"

    mkdir -p "$CLAUDE_DIR/hooks/devtools"
    cp "$REPO_ROOT/scripts/hooks/"*.py "$CLAUDE_DIR/hooks/devtools/"
    wire_global_hooks "$CLAUDE_DIR/settings.json"
    exit 0
fi

DEST="$1"
if [ ! -d "$DEST" ]; then
    echo "Error: '$DEST' is not a directory" >&2
    exit 1
fi

mkdir -p "$DEST/scripts/hooks"

install_claude_skills "$DEST/.claude/skills"
install_codex_skills "$DEST/.codex/skills"
echo "Skipped in-progress skills: ${IN_PROGRESS_SKILLS[*]:-(none)}"

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

tidy_skills "$DEST/.claude/skills" "$DEST/.codex/skills"
rm -rf "$DEST/scripts/hooks/__pycache__"

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
