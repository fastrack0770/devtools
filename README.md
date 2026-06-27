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
- `.claude/skills/` — methodology skills (TDD, code review, planning, security, openspec, …). Taken from https://github.com/addyosmani/agent-skills
- `.claude/commands/opsx/` — openspec slash commands (`/opsx:propose|apply|sync|archive|explore`).
- `.claude/settings.json` — wires the two hooks below (uses `CLAUDE_PROJECT_DIR`, so it's portable).
- `scripts/hooks/skill_suggest.py` — `UserPromptSubmit` hook; suggests relevant skills by keyword (RU/EN).
- `scripts/hooks/opsx_skill_routing.py` — `PostToolUse` hook; reminds about phase skills when an openspec skill runs.

`.claude/settings.local.json` is machine/project-specific (permissions) — not part of the portable base.

## Deploy

```sh
deploy/claude-config.sh <project-dir>
```

Copies `.claude/skills`, `.claude/settings.json` and `scripts/hooks/*.py`
into `<project-dir>`. If the project already has a `.claude/settings.json`, it is left
untouched — merge the `hooks` block manually. The `opsx` slash commands are not copied —
run `openspec init` in the target project to generate them.

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
