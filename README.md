# devtools

Two independent toolkits:

- **[Claude Code base config](#claude-code-base-config)** — reusable Claude Code setup for any project.
- **[Bash scripts](#bash-scripts)** — small git/workspace helpers for your terminal.

Each ships its own deploy script in `deploy/`.

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
