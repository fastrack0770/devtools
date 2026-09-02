# devtools

Three independent toolkits:

- **[Bash scripts](#bash-scripts)** — small git/workspace helpers for your terminal.
- **[Coding-agent base config](#coding-agent-base-config)** — reusable Claude Code + Codex setup for any project.
- **[GNOME Shell extension](#gnome-shell-extension)** — Claude Code and Codex usage indicators in the Ubuntu top panel.

Each ships its own deploy script in `deploy/`; the `Makefile` wraps all three.

## Install

```sh
make                                            # list the components
make install bash-scripts                       # 1. console utilities
make install ai-config PROJECT=/path/to/project # 2. Claude Code + Codex configuration
make install gnome-extension                    # 3. Ubuntu extension
```

Components combine: `make install bash-scripts gnome-extension`. Bare `make install`
takes all three, but skips the agent config unless `PROJECT` is set
(`make install PROJECT=/path/to/project`). Every component is idempotent.

`make uninstall bash-scripts` and `make uninstall gnome-extension` reverse the first
and third; the agent config has no uninstaller, since by then its files are part
of the target project.

---

# Coding-agent base config

Reusable, project-agnostic agent setup in `.claude/`, `.codex/` and `scripts/hooks/`.
Drop it into any project to get the same skills, slash commands and skill-routing hooks
— for Claude Code and for Codex.

> Renamed from `claude-config` once it started carrying the Codex side as well.
> `make install claude-config PROJECT=…` still works and prints a notice, and a
> `CLAUDE.md` written by the old script is migrated to the new marker on the next run.

Contents:
- `.claude/skill-manifest.json` — the release boundary: promoted skills deploy; the `retro` in-progress bucket stays here for piloting.
- `.claude/skills/` — methodology skills grouped by the router: main-flow `grilling`; on-ramps `prototype`, `resolving-merge-conflicts`, and `parallel-dev`; codebase-health `codebase-design`; vocabulary `domain-modeling` and `writing-for-agents`; production helper `wizard`; and human-invoked `handoff`, `retro`, and `to-questionnaire`. Each skill keeps its nested `scripts/`, `references/`, and templates. Adapted from both https://github.com/addyosmani/agent-skills and https://github.com/mattpocock/skills.
- `.claude/commands/opsx/` — openspec slash commands (`/opsx:propose|apply|sync|archive|explore`).
- `.claude/opsx/` — ideation lenses and the refinement rubric that both explore skills point at.
- `.codex/skills/` — the openspec workflow for Codex; at deploy time `deploy/ai-config.sh` adds the promoted model-invoked methodology skills next to it (Codex parity), leaving out `parallel-dev` and the human-invoked skills. The openspec copies keep their Codex-specific tools (`update_plan` instead of `TodoWrite`, plain questions instead of `AskUserQuestion`, sync inline instead of through a subagent).
- `.claude/settings.json` — wires the two hooks below (uses `CLAUDE_PROJECT_DIR`, so it's portable).
- `scripts/hooks/skill_suggest.py` — `UserPromptSubmit` hook; suggests relevant skills by keyword (RU/EN).
- `scripts/hooks/opsx_skill_routing.py` — `PostToolUse` hook; reminds about phase skills when an openspec skill runs.
- `CLAUDE.md` — base working rules (act on the skill-routing hooks; don't spawn agents outside `parallel-dev`). The single source of truth for every agent: rule changes are made here.
- `.codex/AGENTS.md` → deployed as `AGENTS.md` — the file Codex reads. It only points at `CLAUDE.md` (plus one note that the hook machinery does not fire in a Codex session), so the rules never exist in two versions.
- `docs/adr/` — short records for durable configuration and routing decisions.

`.claude/settings.local.json` is machine/project-specific (permissions) — not part of the portable base.

The `openspec-*` skills (both trees) and `.claude/commands/opsx/` **are committed here**
(they are tuned for this repo's skill set, not stock `openspec init` output) and no longer
gitignored. Re-running `openspec init` in this repo therefore shows up as modified tracked
files — diff before keeping it, or the local tuning is silently reverted. The local tuning
sits in `<!-- BEGIN custom addition -->` blocks so it can be restored after a regeneration.

## Deploy

```sh
deploy/ai-config.sh <project-dir>
```

Copies promoted `.claude/skills` (with each skill's nested `scripts/`, `references/`
and templates), `.claude/commands` (the `opsx` slash commands), `.claude/opsx`,
the Codex-parity skill set, `.claude/settings.json`, `scripts/hooks/*.py`, `CLAUDE.md` and
`AGENTS.md` into `<project-dir>`. Executable bits on skill scripts are restored after the
copy and any `__pycache__`/`*.pyc` is stripped. If the project already has a
`.claude/settings.json`, it is left untouched — merge the `hooks` block manually. Running
`openspec init` in the target project will regenerate the `opsx` commands if you need a
newer version.

Codex never sees `CLAUDE.md`, so it gets `AGENTS.md` — a pointer to `CLAUDE.md`, not a
copy of it. The skill-routing hooks stay Claude-only (Codex has no equivalent wired here);
`AGENTS.md` says as much, so a Codex session picks its skills itself.

**Re-run it to pull skill updates into a project** — that is the intended update path,
so the deploy is idempotent. In `CLAUDE.md` the base rules live in a managed block:

```markdown
<!-- BEGIN devtools base rules — managed by deploy/ai-config.sh -->
…working rules…
<!-- END devtools base rules -->
```

`AGENTS.md` works the same way, with its own `devtools codex rules` markers. Re-runs
replace the block in place; anything you wrote outside it is left alone. Edits *inside*
the block are overwritten, so keep project-specific rules below the `END` marker. Older
layouts are migrated on the next run — the pre-rename
`managed by deploy/claude-config.sh` opening line is rewritten, and unmarked copies
stacked at the top are collapsed into one block.

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

To undo it:

```sh
deploy/bash-scripts-uninstall.sh
```

Strips the `PATH` block back out of the same rc file, backing it up to
`<rc>.devtools.bak` first. The scripts stay in the repo — only the shell hook goes.

---

# GNOME Shell extension

`gnome-extension/ai-usage@ai-usage-control` — top-panel indicators showing how much of
your coding-agent usage limits you have consumed, one bar per CLI: a progress bar for
the shortest limit window (blue < 75 %, yellow 75–90 %, red 90–100 %), the countdown to
the reset, any further windows and quotas in the menu, and threshold notifications.

Supports **Claude Code** and **Codex**. There is no settings UI: a bar appears when that
CLI is logged in and disappears when it is not, rechecked every minute.

Requires GNOME Shell 42 (Ubuntu 22.04), `python3` and at least one logged-in CLI. The
Claude helper reads (and, when the token expires, refreshes) `~/.claude/.credentials.json`;
the Codex helper never touches `~/.codex/auth.json` — it asks `codex app-server` instead,
falling back to a dimmed, explicitly stale reading from the session journal. See
[gnome-extension/README.md](gnome-extension/README.md) for the data sources, the security
notes, the tests and debugging commands.

> Renamed from `claude-usage@claude-usage-control`. The deploy script removes the old
> install automatically — without that you would see two Claude bars.

## Deploy

```sh
deploy/gnome-extension.sh
```

Copies the extension into `~/.local/share/gnome-shell/extensions/` and enables it.
**Log out and log back in** afterwards — on Wayland GNOME Shell cannot pick up a new
extension in place. Remove it with `make uninstall gnome-extension`.
