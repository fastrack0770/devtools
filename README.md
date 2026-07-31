# devtools

Three independent toolkits:

- **[Bash scripts](#bash-scripts)** — small git/workspace helpers for your terminal.
- **[Claude Code base config](#claude-code-base-config)** — reusable Claude Code setup for any project.
- **[GNOME Shell extension](#gnome-shell-extension)** — Claude Code usage indicator in the Ubuntu top panel.

Each ships its own deploy script in `deploy/`; the `Makefile` wraps all three.

## Install

```sh
make                                        # list the targets
make bash-scripts                           # 1. console utilities
make claude-config PROJECT=/path/to/project # 2. Claude Code configuration
make gnome-extension                        # 3. Ubuntu extension
```

`make install` runs all three at once; it only deploys the Claude Code config when
`PROJECT` is set (`make install PROJECT=/path/to/project`). Every target is idempotent.

---

# Claude Code base config

Reusable, project-agnostic Claude Code setup in `.claude/` and `scripts/hooks/`.
Drop it into any project to get the same skills, slash commands and skill-routing hooks.

Contents:
- `.claude/skills/` — methodology skills (TDD, code review, planning, security, openspec, …), including each skill's own `scripts/`, `references/` and templates. Taken from https://github.com/addyosmani/agent-skills
- `.claude/commands/opsx/` — openspec slash commands (`/opsx:propose|apply|sync|archive|explore`).
- `.claude/settings.json` — wires the two hooks below (uses `CLAUDE_PROJECT_DIR`, so it's portable).
- `scripts/hooks/skill_suggest.py` — `UserPromptSubmit` hook; suggests relevant skills by keyword (RU/EN).
- `scripts/hooks/opsx_skill_routing.py` — `PostToolUse` hook; reminds about phase skills when an openspec skill runs.
- `CLAUDE.md` — base working rules (act on the skill-routing hooks; don't spawn agents outside `parallel-dev`).

`.claude/settings.local.json` is machine/project-specific (permissions) — not part of the portable base.

## Deploy

```sh
deploy/claude-config.sh <project-dir>
```

Copies `.claude/skills` (with each skill's nested `scripts/`, `references/` and
templates), `.claude/commands` (the `opsx` slash commands), `.claude/settings.json`,
`scripts/hooks/*.py` and `CLAUDE.md` into `<project-dir>`. Executable bits on skill
scripts are restored after the copy and any `__pycache__`/`*.pyc` is stripped. If the
project already has a `.claude/settings.json`, it is left untouched — merge the `hooks`
block manually. If the project already has a `CLAUDE.md`, the base rules are prepended
to it; otherwise it is copied. Running `openspec init` in the target project will
regenerate the `opsx` commands if you need a newer version.

---

# Bash scripts

Small git/workspace helpers in `bash/bin`.

- `cleangitws`  — go to the `master`/`main` branch, pull recent changes, delete stale remote and local branches
- `gitclean`  — clean git workspace
- `gitmb`  — make new branch, push it to the remote origin
- `gitprune`  — prune stale remote branches
- `gitremove`  — remove stale local branches
- `gitupdate`  — update git submodules recursively
- `makeexec`  — create a text file and make it executable
- `source_ros`  — source the ROS environment

## Deploy

```sh
deploy/bash-scripts.sh
```

Adds `bash/bin` to your `PATH` (via `~/.bashrc` or `~/.zshrc`) so the scripts are
callable by name in any terminal. Idempotent. Run `source ~/.bashrc` (or open a new
terminal) afterwards.

---

# GNOME Shell extension

`gnome-extension/claude-usage@claude-usage-control` — a top-panel indicator showing how
much of your Claude Code usage limits you have consumed: a progress bar for the current
5-hour session (blue < 75 %, yellow 75–90 %, red 90–100 %), the countdown to the limit
reset, the used share of the model-scoped weekly quota, and threshold notifications.

Requires GNOME Shell 42 (Ubuntu 22.04), `python3` and a logged-in Claude Code CLI. The
helper reads (and, when the token expires, refreshes) `~/.claude/.credentials.json` —
see [gnome-extension/README.md](gnome-extension/README.md) for the data source, the
security notes and debugging commands.

## Deploy

```sh
deploy/gnome-extension.sh
```

Copies the extension into `~/.local/share/gnome-shell/extensions/` and enables it.
**Log out and log back in** afterwards — on Wayland GNOME Shell cannot pick up a new
extension in place. Remove it with `make uninstall-gnome-extension`.
