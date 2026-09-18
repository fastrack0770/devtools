# Working rules (Codex)

The rules for this project are in **[CLAUDE.md](CLAUDE.md)** — read that file at the start
of the session and follow it. Despite the name it is not Claude-only: it is the single
source of truth for every agent working here, this one included.

Nothing is restated here, and nothing is edited here: rule changes go into `CLAUDE.md`.

One translation note. Where `CLAUDE.md` relies on Claude Code machinery — the
`UserPromptSubmit` / `PostToolUse` skill-routing hooks, the Skill tool — the intent still
binds you, the mechanism does not: no hook hands you a `[skill-routing]` line, so you pick
the skill yourself, and you load one by reading its file (`.codex/skills/<name>/SKILL.md`,
discovered automatically, or `.claude/skills/<name>/SKILL.md`, plain Markdown).
