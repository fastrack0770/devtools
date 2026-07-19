---
name: parallel-dev
description: Parallel development orchestration — splits implementation work into threads with non-overlapping file sets, hands some threads to subagents while the main model takes the largest thread itself. Invoke on /parallel-dev, and also whenever the user asks to "parallelize", "split the work", "use multiple agents", "fan out the work", or when implementing a large change with independent groups of files (several screens, layers, or modules at once). Accepts an optional argument — the number of threads (default 2, one agent + the main model).
---

# Parallel development

Rules for dividing implementation work between subagents (Agent tool) and the main model. The goal is speedup without conflicting edits, so the core invariant is: **the file sets of the threads must not overlap**.

Bundled resources (paths relative to this skill's directory, `.claude/skills/parallel-dev/`):

- `scripts/check_partition.py` — deterministic validation of the partition and audit of the agents' actual changes. Use it instead of eyeballing file lists.
- `references/agent-prompt-template.md` — the template every agent prompt is built from. Read it when composing prompts.

## Arguments

`/parallel-dev [N] [task description]`

- `N` — number of threads, default **2**.
- N threads = (N−1) concurrent agents + one thread for the main model. Example: N=5 → up to 4 agents in parallel, the fifth thread is done by the main model itself.

## Step 1. Partitioning and the plan file

Before launching any agents, build a partitioning plan:

1. List every file the task will touch (both created and modified).
2. Group the work into threads with non-overlapping file sets. Pay special attention to "hub" files that almost every task edits: the version catalog and `build.gradle.kts`, DI modules, resources/strings, navigation, shared data models. Two pieces of work that edit the same hub belong to one thread; alternatively, defer all hub edits into `deferred_hub_edits` and let the main model apply them during the merge step.
3. Estimate the size of each thread (number of files and complexity of the edits).
4. **Write the plan to disk** as `parallel-dev-plan.json` in the session scratchpad directory (listed in your system prompt; fall back to `/tmp` if none). The plan file is the single source of truth for the whole run: unlike the conversation, it survives `/compact` verbatim. Keep it updated for the entire run — statuses, agent summaries, actual files.

Plan format (statuses: `pending` / `running` / `done`; `executor`: `main` / `agent`):

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
      "summary": null,
      "actual_files": []
    }
  ],
  "deferred_hub_edits": ["app/src/main/res/values/strings.xml"],
  "contracts": [
    {
      "between": ["data-layer", "login-ui"],
      "definition": "interface signatures, verbatim Kotlin"
    }
  ]
}
```

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
- Build each agent's prompt from `references/agent-prompt-template.md`, filling every placeholder (task context, allowed files, contracts, verification commands), and store the finished prompts in the plan file (`threads[].prompt`). The template carries the non-negotiables — `using-agent-skills` bootstrap, the file boundary, the subagent ban that overrides any skill's fan-out suggestions, and the FILES CHANGED / SUMMARY / DEVIATIONS response format — do not strip them when filling it in.

## Step 4. Checkpoint: ask the user to run /compact

At the very last moment before launching the parallel agents — when the plan file is written and validated and the agent prompts are stored in it — stop and end your turn. Explicitly ask the user to run `/compact` and to send a follow-up message when it is done. `/compact` is a user-side command; you cannot run it yourself, so you must pause and wait. Rationale: the launch starts a long autonomous phase (agents working + merge + build), and compacting right before it frees the context for that phase instead of wasting it on the already-digested planning discussion.

That same final message must contain:

- a summary of the final plan (threads, file sets, who does what) so the user can sanity-check it before compaction;
- **a markdown link to the plan file** (absolute path) — mandatory, no exceptions: after compaction the plan is re-read from this file, not reconstructed from the conversation summary.

After the user returns, re-read the plan file (and this SKILL.md if its instructions are no longer verbatim in context), then launch the first wave immediately without re-deriving anything.

## Step 5. Launching agents

Immediately before the launch:

1. Re-validate the partition (the plan may have been edited): `check_partition.py check <plan>`.
2. Record pre-existing working-tree changes so the final audit can exclude them: `check_partition.py snapshot <plan>`.

Launch all agents of a wave in a single message (parallel tool calls), each with its prepared prompt from the plan file. Agents work in the shared working tree — this is safe precisely because the file sets do not overlap; the template makes the restriction explicit to each agent.

While the agents work, the main model executes its own thread. Do not poll the agents in a waiting loop — the completion notification arrives on its own. When an agent finishes: record its status, summary, and reported `FILES CHANGED` into the plan file (`status`, `summary`, `actual_files`); then, if the queue is not empty and the context guard allows, launch the next agent.

### Context guard (25% rule)

The main model cannot measure its context precisely, but it can track it approximately by estimating how much of the window the conversation has consumed. When you estimate that **25% or more of the context window has been consumed** (and in any case if a harness low-context warning appears):

1. Stop launching new agents — the queue stays frozen, even if slots are free.
2. Let the already-running agents finish and record their results into the plan file.
3. End the turn and ask the user to run `/compact` (same mechanics as Step 4). The plan file already holds the durable state; the message must still include the markdown link to it plus the current state of your own thread.
4. After the user returns, re-read the plan file (and this SKILL.md if needed), then resume the queue.

Rationale: each agent's results, the merge, and the final build still have to fit in the remaining context; launching new agents into a nearly-full window risks losing their output to mid-flight compaction.

## Step 6. Merge and verification

Once all threads are finished, the main model:

1. Runs the boundary audit: `check_partition.py audit <plan>` — it flags files changed outside the plan and per-thread violations of `actual_files` against the allowed lists. Investigate every violation before anything else.
2. Reviews each agent's diff (`git diff` over its files): conformance to the task, the contracts, and the project style; reconciles any deviations the agents flagged.
3. Applies the deferred "hub" edits (DI registration, strings/resources, navigation, gradle).
4. Runs the full build and the test suite.
5. Reports to the user: how the work was split into threads, what each one did, audit results, and the build/test results.

## If you are a subagent yourself

If these instructions are being read inside a subagent — do not apply them: do the work sequentially yourself. Recursive parallelization is forbidden.
