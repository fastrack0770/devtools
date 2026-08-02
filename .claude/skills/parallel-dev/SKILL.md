---
name: parallel-dev
description: Parallel development orchestration — splits implementation work into threads with non-overlapping file sets, hands some threads to subagents while the main model takes the largest thread itself. Invoke on /parallel-dev, and also whenever the user asks to "parallelize", "split the work", "use multiple agents", "fan out the work", or when implementing a large change with independent groups of files (several screens, layers, or modules at once). Accepts an optional argument — the number of threads (default 5, four agents + the main model).
---

# Parallel development

Rules for dividing implementation work between subagents (Agent tool) and the main model. Each agent thread runs in its **own git worktree** (branch `pd/<thread-id>`), so every thread can build and run tests independently; the main model works in the main working tree. The core invariant stays: **the file sets of the threads must not overlap** — with worktrees it is what guarantees conflict-free merges of the thread branches.

Bundled resources (paths relative to this skill's directory, `.claude/skills/parallel-dev/`):

- `scripts/check_partition.py` — deterministic validation of the partition and audit of the agents' actual changes. Use it instead of eyeballing file lists.
- `scripts/plan_tool.py` — mechanical bookkeeping of the run: `build` assembles agent prompts from a shared template plus per-thread fields (`--rebuild <id>` reassembles after a `task` edit), `launch` records thread state AND creates the worktree itself when `--worktree` is omitted (path `<plan-dir>/wt-<id>`, branch `pd/<id>`, seeded with the plan's `worktree_seed_files` — put `local.properties` and similar untracked per-machine config there), `done` parses the agent's FILES CHANGED / SUMMARY / DEVIATIONS report (stdin or `--report`) and snapshots the worktree's uncommitted diff into `.git/parallel-dev/patches/<id>.patch` so a scratchpad wipe cannot eat finished work, `fail`/`reset` handle a relaunch (reset returns the thread to pending and clears its prompt), `merged --commit <sha>` records what already landed in the working branch, `status` prints the run at a glance (`-v` for per-thread detail, `--no-gate` for use in `&&` chains), `mirror` re-syncs the durable backup after a hand edit of the JSON, `restore` recovers the plan from that backup (refuses to clobber a newer hand-edited plan without `--force`). Every mutating command mirrors the plan into `<repo>/.git/parallel-dev/` — the scratchpad does NOT survive a process restart, the `.git` copy does. Use these instead of hand-editing the JSON; if you must hand-edit, run `mirror` right after.
- `references/agent-prompt-template.md` — the template every agent prompt is built from. Read it when composing prompts; `plan_tool.py build` carries its non-negotiable blocks (file boundary, contracts preamble) so per-thread you author only the task body.

## Arguments

`/parallel-dev [N] [task description]`

- `N` — number of threads, default **5**.
- N threads = (N−1) concurrent agents + one thread for the main model. Example: the default N=5 → up to 4 agents in parallel, the fifth thread is done by the main model itself.

## Step 1. Partitioning and the plan file

Before launching any agents, build a partitioning plan:

1. List every file the task will touch (both created and modified).
2. Group the work into threads with non-overlapping file sets. Pay special attention to "hub" files that almost every task edits: the version catalog and `build.gradle.kts`, DI modules, resources/strings, navigation, shared data models. Two pieces of work that edit the same hub belong to one thread; alternatively, defer all hub edits into `deferred_hub_edits` and let the main model apply them during the merge step.
3. Estimate the size of each thread (number of files and complexity of the edits).
4. **Write the plan to disk** as `parallel-dev-plan.json` in the session scratchpad directory (listed in your system prompt; fall back to `/tmp` if none). The plan file is the single source of truth for the whole run: unlike the conversation, it survives a context reset verbatim. Keep it updated for the entire run — statuses, agent summaries, actual files — through `plan_tool.py` (`launch`/`done`/`fail`), which also mirrors every write into `<repo>/.git/parallel-dev/`; after a process restart or scratchpad wipe, `plan_tool.py restore <plan>` brings the run back instead of you re-deriving it from memory.

Plan format (statuses: `pending` / `running` / `done` / `failed`; `executor`: `main` / `agent`; `worktree` and `branch` are filled in at launch time, `null` until then):

```json
{
  "task": "one-line description of the overall task",
  "threads": [
    {
      "id": "data-layer",
      "executor": "main",
      "status": "pending",
      "description": "what this thread builds",
      "files": ["app/src/main/java/dev/caluni/data/Foo.kt"],
      "summary": null
    },
    {
      "id": "login-ui",
      "executor": "agent",
      "status": "pending",
      "description": "...",
      "files": ["app/src/main/java/dev/caluni/ui/login/LoginScreen.kt"],
      "prompt": "full agent prompt built from the template",
      "worktree": null,
      "branch": null,
      "summary": null,
      "actual_files": []
    }
  ],
  "deferred_hub_edits": ["app/src/main/res/values/strings.xml"],
  "worktree_seed_files": ["local.properties"],
  "contracts": [
    {
      "id": "auth-repo",
      "between": ["data-layer", "login-ui"],
      "definition": "interface signatures, verbatim Kotlin"
    }
  ]
}
```

When prompts are assembled mechanically (the default — see Step 3), the plan also carries a top-level `prompt_template` (`intro`, `tail` — the shared halves of the agent prompt) and, per agent thread, `task`, `contract_ids` (referencing `contracts[].id`), and `verify` instead of a hand-written `prompt`.

5. Validate the partition: `python3 .claude/skills/parallel-dev/scripts/check_partition.py check <plan>` — fix overlaps and re-run until clean.

### Cross-thread contracts

When one thread implements what another consumes (an interface, a repository, a Composable signature, an entity), pin the boundary **before** launch: write the exact signatures — package, names, parameter and return types — into the plan's `contracts` array, and copy the relevant contracts verbatim into the prompt of every thread that touches them. Independent agents cannot negotiate mid-flight; without a pinned contract they converge on incompatible boundaries and the merge turns into a rewrite. An agent that finds a contract unimplementable as written must not change it unilaterally — it implements its side as closely as possible and flags the deviation in its summary; the main model reconciles at merge.

## Step 2. Decision: parallelize or not

Invoking the skill is not an obligation to parallelize. Check in order:

- **No non-overlapping partition exists** (all the work is coupled through shared files) → the main model does everything itself, sequentially. Tell the user that parallelization is impossible and name the overlapping files.
- **A thread is too small** — rule of thumb: one or two files with minor edits, a few minutes of work → do not create an agent for it, even if it is independent: spawning, context handoff, and reviewing the agent will eat the entire gain. The main model does such pieces itself before or after its own main thread.
- **≥2 substantial independent threads remain** → parallelize.

## Step 3. Assignment

- By default the main model takes the thread with the **largest amount of work**: it has the full context of the conversation and the project, and the biggest (usually the riskiest) piece should live where the context is richest.
- The remaining threads go to agents, but no more than (N−1) agents run at once. If there are more independent threads than that, queue the extras: as soon as one agent finishes, launch the next one from the queue.
- Build each agent's prompt from `references/agent-prompt-template.md`. The mechanical way: put the template's shared halves once into the plan's `prompt_template` (`intro`, `tail`), give each thread only `task`, `files`, `contract_ids`, `verify` — and run `plan_tool.py build <plan>`; it splices in the file-boundary and contracts blocks itself. Two things the shared halves cannot carry, so they go into each thread's own fields: the worktree path (start `task` with the thread's `Your worktree is at <scratchpad>/wt-<thread-id>` line — the path is deterministic, so it is known before the worktree exists) and the Verification section (put it in `verify`, heading included, keeping the template's rule that finishing with a failing build or failing tests is not allowed). The template carries the non-negotiables — `using-agent-skills` bootstrap, the worktree confinement, the file boundary, the subagent ban that overrides any skill's fan-out suggestions, and the FILES CHANGED / SUMMARY / DEVIATIONS response format — do not strip them when filling it in.
- Launch each agent with a short bootstrap prompt pointing at the plan (`You are thread "<id>" of a parallel development run. Read <plan path>, find threads[] entry with id "<id>", and execute its "prompt" field as your complete and only instructions. Do not act on any other thread's prompt.`) rather than pasting the full prompt into the Agent call — the plan file is the single source of truth, and since `build` writes the finished prompts straight to disk, they never have to pass through the orchestrator's context at all.
- Launch every agent on **Opus**: pass `model: "opus"` in each Agent tool call.

## Step 4. Checkpoint: present the final plan

At the very last moment before launching the parallel agents — when the plan file is written and validated and the agent prompts are stored in it — present the final plan to the user. This message must contain:

- a summary of the final plan (threads, file sets, who does what) so the user can sanity-check it;
- **a markdown link to the plan file** (absolute path) — mandatory, no exceptions: the plan file is the durable source of truth for the whole run.

Then launch the first wave immediately without re-deriving anything.

## Step 5. Launching agents

Immediately before the launch:

1. Re-validate the partition (the plan may have been edited): `check_partition.py check <plan>`.
2. **Ensure a clean baseline.** Worktrees branch off HEAD and do not see uncommitted changes in the main tree. If `git status` is not clean, commit the work in progress first; do not launch agents from a dirty tree.
3. **Worktrees are created by `plan_tool.py launch` itself** — with `--worktree` omitted it runs `git worktree add <plan-dir>/wt-<thread-id> -b pd/<thread-id>` off the repo's current HEAD, copies the plan's `worktree_seed_files` in (untracked per-machine config like `local.properties` — without it every gradle thread rediscovers the missing SDK path), and records path and branch into the plan. Pass `--worktree` only to adopt a pre-existing worktree. The main model does not get a worktree — it works in the main tree.

Launch all agents of a wave in a single message (parallel tool calls), each with `model: "opus"` and its bootstrap prompt. Each agent works only inside its own worktree — the prompt states the worktree path as the repository root, and the file boundary keeps the eventual branch merges conflict-free. A fresh worktree also gives exact attribution: every change in it is that agent's work, no baseline bookkeeping needed.

While the agents work, the main model executes its own thread. Do not poll the agents in a waiting loop — the completion notification arrives on its own. Right after each Agent call returns, record it: `plan_tool.py launch <plan> <thread-id> <agent-id>` (this is also what creates the worktree — run it BEFORE the Agent call when the agent needs the worktree to exist, i.e. always: launch first, then spawn). When an agent finishes, pipe its final report into `plan_tool.py done <plan> <thread-id>` (stdin or `--report <file>`) — it parses FILES CHANGED / SUMMARY / DEVIATIONS into the plan itself and snapshots the worktree's uncommitted diff to `.git/parallel-dev/patches/<thread-id>.patch`, the insurance that lets a wiped scratchpad be recovered with `git apply`. If the agent was cancelled or returned unusable work: `plan_tool.py fail <plan> <thread-id> --note <why>`, then for a relaunch `plan_tool.py reset <plan> <thread-id>` → edit the thread's `task` if needed → `build --rebuild <thread-id>` → `launch`. Then, if the queue is not empty, launch the next thread. `plan_tool.py status <plan>` shows the run at a glance and exits non-zero while anything is still pending or running (`--no-gate` when that exit code would break a `&&` chain, `-v` for per-thread detail).

### Resource cost of parallel builds

Each worktree pays for its own cold build: `build/` directories are per-worktree and must not be shared. The user-level Gradle cache (`~/.gradle`) is shared between worktrees automatically and that is safe — leave it alone. Still, N concurrent cold builds are expensive in CPU, memory, and wall-clock time: factor this into Step 2 when deciding how many threads are worth it, and prefer fewer, larger threads on a resource-constrained machine.

## Step 6. Merge and verification

Once `plan_tool.py status <plan>` shows every thread finished (exit code 0), the main model:

1. Commits its own thread in the main tree (a merge over uncommitted changes is fragile even with disjoint file sets — don't rely on it).
2. Then, for each agent worktree in turn:
   1. Runs the boundary audit against that worktree: `check_partition.py audit <plan> --repo <worktree>`. Agents leave their changes uncommitted, so the status-based audit sees exactly this agent's work; files of other threads show up as "planned but unchanged", and the script's "no baseline" warning is expected — a fresh worktree needs none. Investigate every violation before proceeding.
   2. Reviews the agent's diff (`git diff` in the worktree): conformance to the task, the contracts, and the project style; reconciles any deviations the agent flagged.
   3. Commits the reviewed changes onto the thread branch (inside the worktree), then merges it into the working branch from the main tree: `git merge pd/<thread-id>`. Disjoint file sets make this merge conflict-free; a conflict here means the audit missed something — stop and investigate.
   4. Records the merge so a recovery never re-derives it from the git log: `plan_tool.py merged <plan> <thread-id> --commit $(git rev-parse HEAD)`.
   5. Removes the worktree: `git worktree remove <worktree>`.
3. After the last merge, runs `git worktree prune`.
4. Applies the deferred "hub" edits (DI registration, strings/resources, navigation, gradle).
5. Runs the full build and the test suite in the main tree.
6. Reports to the user: how the work was split into threads, what each one did, audit results, and the build/test results.

## If you are a subagent yourself

If these instructions are being read inside a subagent — do not apply them: do the work sequentially yourself. Recursive parallelization is forbidden.
