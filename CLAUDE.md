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

## 2. Delegation rules: `parallel-dev` owns the agent quota; a plan is needed only for delegated file changes

A delegate is any model working for the main one: an Agent tool subagent **or an MCP
consultation (codex, another Claude model) — codex counts as an agent**.

**Strong request:** never spawn delegates outside these rules.

- **Delegating file changes** — any delegate that may create, modify, delete, or
  move files, or otherwise change repo/git state — requires `parallel-dev` initiated
  (via `/parallel-dev`, or when the user explicitly asks to parallelize / split /
  fan out the work) and its partitioning plan (`parallel-dev-plan.json`) written and
  validated before that delegate launches, even for a single agent. The boundary is
  effects, not labels: a "review" or "advisory" delegate that is allowed to write
  files is a mutating delegate. Mutating delegation goes through the Agent tool
  only — MCP consultations are always launched read-only.
- **Running delegates in parallel** (more than one at once, read-only ones included)
  also requires `parallel-dev`: it owns the concurrency quota — at most N−1
  concurrent delegates (default 4), codex consultations included. If no delegate
  is handed file changes, no plan is needed; only the quota applies.
- **A single sequential read-only delegate** (a codex second opinion, an `Explore`
  lookup) needs neither the skill nor a plan.
- Launch plan-free delegates read-only: prefer enforced forms (`Explore`/`Plan`
  agent types, codex with `sandbox: read-only`); only when a general agent is
  needed, explicitly forbid writes in its prompt. A read-only delegate that
  concludes edits are needed stops and reports; the main model applies the edits
  itself or delegates them under a validated plan.
