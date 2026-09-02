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

## 2. Delegation rules: `parallel-dev` is the sole authority for the concurrent-delegate quota; a plan is needed only for delegated file changes

A delegate is any model working for the main one: an Agent tool subagent **or an
external CLI/MCP session (codex, another Claude model) — codex counts as an agent**.
Rationale: see `docs/adr/0001-codex-is-a-delegate.md`.

**Strong request:** never spawn delegates outside these rules.

### Authority and precedence

`parallel-dev` is the sole source of truth for the permitted number of concurrent
delegates. When the skill is loaded, its resolved quota governs — this file states no
numeric ceiling of its own and must not be read as imposing one. The resolution order
is defined in that skill's "Quota authority and resolution" section; follow it exactly.

Fallback, and only when the skill cannot be loaded: fail closed — no concurrent
delegates and no delegated file changes. A single sequential read-only delegate remains
allowed. This fallback never applies once `parallel-dev` is loaded.

Tool or platform capacity may force delegates to be queued; that does not lower the
quota the skill resolved, and must not be read as a lower policy limit.
Quota rationale: see `docs/adr/0002-parallel-dev-owns-the-delegate-quota.md`.

### Delegation gate

- **Delegating file changes** — any delegate that may create, modify, delete, or
  move files, or otherwise change repo/git state — requires `parallel-dev` initiated
  (via `/parallel-dev`, or when the user explicitly asks to parallelize / split /
  fan out the work) and its partitioning plan (`parallel-dev-plan.json`) written and
  validated before that delegate launches, even for a single agent. The boundary is
  effects, not labels: a "review" or "advisory" delegate that is allowed to write
  files is a mutating delegate. A mutating delegate may be carried either by the
  Agent tool or by codex — codex is a full code-editing executor, not advisory-only.
  Launch it through `.claude/skills/parallel-dev/scripts/run_codex.sh --write --cwd
  <thread worktree>`; that mode is allowed only under a validated plan.
- **Running delegates concurrently** — more than one at once, read-only ones and codex
  consultations included — also requires `parallel-dev`: the skill resolves and owns
  the concurrency quota. If no delegate is handed file changes, no plan is needed;
  only the skill-resolved quota applies.
- **A single sequential read-only delegate** (a codex second opinion, an `Explore`
  lookup) needs neither the skill nor a plan.
- Launch plan-free delegates read-only: prefer enforced forms (`Explore`/`Plan`
  agent types, `run_codex.sh` without `--write` — its default read-only mode is the
  one for reviews and second opinions); only when a general agent is needed,
  explicitly forbid writes in its prompt. A read-only delegate that
  concludes edits are needed stops and reports; the main model applies the edits
  itself or delegates them under a validated plan.

## 3. Editing skills or agent docs

Run `python3 scripts/check_skills.py` after any change under `.claude/skills/`,
`scripts/hooks/`, or `.claude/skill-manifest.json`. When writing or editing a skill,
Call the Skill tool with "writing-for-agents". New skills enter the manifest as
in-progress until they have been used on a real task.
