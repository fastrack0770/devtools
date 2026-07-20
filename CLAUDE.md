# Working rules

## 1. Follow the skill routine the hooks are waiting for

This project wires two skill-routing hooks (see `.claude/settings.json`):

- `UserPromptSubmit` → `scripts/hooks/skill_suggest.py` — on every prompt, injects a
  `[skill-routing]` line suggesting the skills relevant to that message.
- `PostToolUse` (matcher `Skill`) → `scripts/hooks/opsx_skill_routing.py` — after an
  openspec skill runs, reminds you of the next-phase skill.

These hooks are **waiting for you to act on their output**. Treat every skill
suggestion as a routing instruction, not noise: when a hook names a skill that fits
the task, invoke it via the Skill tool before doing the work by hand. When in doubt,
start with `using-agent-skills`. Do not ignore the suggestions and improvise.

## 2. Do not use the Agent tool unless `parallel-dev` was initiated

**Strong request:** never spawn subagents with the Agent tool on your own initiative.
The only sanctioned path to running agents is the `parallel-dev` skill.

- Launch agents **only** after the `parallel-dev` skill has been initiated (via
  `/parallel-dev`, or when the user explicitly asks to parallelize / split / fan out
  the work) and its partitioning plan (`parallel-dev-plan.json`) exists.
- Outside of an active `parallel-dev` run, do the work in the main thread yourself.
  Do not delegate to `general-purpose`, `Explore`, `Plan`, or any other agent as a
  shortcut.
- If a task feels large enough to want agents, invoke `parallel-dev` first — that skill
  owns the non-overlapping file partitioning that makes parallel agents safe.
