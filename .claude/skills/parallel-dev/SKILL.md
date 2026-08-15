---
name: parallel-dev
description: Parallel development orchestration — splits implementation work into threads with non-overlapping file sets, hands some threads to delegates (Agent tool subagents or codex sessions launched via scripts/run_codex.sh --write, which edit code just like subagents) while the main model takes the largest thread itself. Invoke on /parallel-dev, and also whenever the user asks to "parallelize", "split the work", "use multiple agents", "fan out the work", or when implementing a large change with independent groups of files (several screens, layers, or modules at once). Also governs plan-free parallel delegation — running read-only delegates (research, reviews, codex second opinions) concurrently uses this skill's agent quota without a partitioning plan; codex runs count as agents. Accepts an optional argument — the number of threads (default 5, four agents + the main model).
---

# Parallel development

## Quota authority and resolution

This skill is the sole source of truth for the concurrent-delegate quota. `CLAUDE.md`
provides the gate that requires this skill for concurrent delegation and expressly
delegates the number to this section. Once this skill is loaded, do not apply any
numeric fallback, remembered default, or inferred lower ceiling — neither from
`CLAUDE.md` nor from an earlier run.

Resolve `N` exactly once, in this order:

1. an explicit numeric argument to `/parallel-dev N`;
2. an explicit number in the user's current request;
3. the default `N = 5`.

`N` counts execution threads: one thread for the main model plus up to `N−1` delegates
running concurrently. So `/parallel-dev 8` permits seven concurrent delegates. Units
matter, so read the user's number for what it counts: `K agents` or `K delegates` means
`N = K+1`; `K threads` means `N = K`.

Record the resolved value in the plan as `parallelism.total_threads`, with
`parallelism.max_concurrent_delegates = total_threads − 1`, and state both in the
checkpoint before launch (Step 4). Do not silently reduce them because a lower number
appears elsewhere, because a smaller wave feels safer, or because an earlier run used
the default.

The quota is a maximum, not a target to fill: the partitioning rules may yield fewer
substantial independent threads, and tool or platform capacity may force eligible
delegates to be queued. In either case say why the active wave is smaller — do not
redefine the resolved quota.

## Scope and modes

A delegate is any model working for the main one — an Agent tool subagent or an
external CLI/MCP session (codex, another model); codex counts as an agent. A thread that changes
files can be carried either by the Agent tool or by codex — it is a full code-editing
executor here, launched through `scripts/run_codex.sh --write --cwd <worktree>`.
Outside a validated plan codex runs in the script's default read-only mode.
This skill governs all concurrent delegation, in one of two modes:

- **Plan mode** — file changes are delegated: at least one delegate may create,
  modify, delete, or move files, or otherwise change repo/git state. The full flow
  below applies — partitioning plan, validation, worktrees, merge — even for a
  single mutating agent, and regardless of whether that agent is an Agent tool
  subagent or a codex session in `workspace-write`. Whether a delegate is mutating
  is decided by what it is *allowed* to do, not by what it is called: a "review"
  agent permitted to write files is a mutating agent.
- **Plan-free mode** — no delegate touches files (read-only research, reviews, second
  opinions; any edits stay with the main model). No plan, no worktrees, no partition
  check — only the concurrency quota applies. Launch such delegates read-only:
  prefer enforced forms (`Explore`/`Plan` agent types, `run_codex.sh` without `--write`);
  only when a general agent is needed, explicitly forbid writes in its prompt. A
  read-only delegate that concludes edits are needed stops and reports — promoting
  it to a mutating thread happens only by adding the thread to the plan,
  re-validating it, and launching fresh under plan mode.

In both modes the quota is the same: the resolved `parallelism.max_concurrent_delegates`
above, codex consultations included; the main model is not a delegate and takes no
slot. A single sequential read-only consultation does not require this skill at all.
Mixed runs are plan mode: mutating threads go into the plan and its partition;
read-only delegates stay out of the plan and its lifecycle commands (`launch`/`done`,
worktrees, audits) but still occupy quota slots.

The rest of this document describes plan mode.

Rules for dividing implementation work between delegates — Agent tool subagents or codex sessions in `workspace-write` — and the main model. Each delegated thread runs in its **own git worktree** (branch `pd/<thread-id>`), so every thread can build and run tests independently; the main model works in the main working tree. The core invariant stays: **the file sets of the threads must not overlap** — with worktrees it is what guarantees conflict-free merges of the thread branches.

**Branch layout and its end state.** A run never builds directly on the branch it was invoked from. `plan_tool.py start` records that branch as the run's **base branch** and opens the run's own integration branch on top of it (`pd/run-<digest>`, checked out in the main tree); every thread branch forks from there and merges back into it, and the main model's own thread is committed there too. The whole scaffolding is temporary and each level is taken down as soon as it is consumed: a thread branch is deleted the moment it is merged into the run branch (`plan_tool.py merged`), and the run branch is deleted the moment it is merged into the base branch (`plan_tool.py finish`). **The run must end with zero branches created by parallel-dev** — the repository is back on its base branch, carrying the work and nothing else. A leftover `pd/*` branch is a bug in the run, not a harmless remnant.

Bundled resources (paths relative to this skill's directory, `.claude/skills/parallel-dev/`):

- `scripts/check_partition.py` — deterministic validation of the partition (`check`) and audit of the agents' actual changes (`audit --repo <worktree> --thread <id>`, one call per thread worktree). Use it instead of eyeballing file lists.
- `scripts/plan_tool.py` — mechanical bookkeeping of the run: `start` opens the run branch and records the base branch, `finish` closes the run (merges the run branch back into the base branch, deletes it, and reports any surviving `pd/*` branch), `build` assembles agent prompts from a shared template plus per-thread fields (`--rebuild <id>` reassembles after a `task` edit), `launch` records thread state AND creates the worktree itself when `--worktree` is omitted (path `<plan-dir>/wt-<id>`, branch `pd/<id>`, seeded with the plan's `worktree_seed_files` — put `local.properties` and similar untracked per-machine config there), `done` parses the agent's FILES CHANGED / SUMMARY / DEVIATIONS report (stdin or `--report`; a report that yields no FILES CHANGED entries is an error unless `--allow-unparsed`) and snapshots the worktree's uncommitted diff — staged, unstaged and untracked — into `.git/parallel-dev/patches/<slot>/<id>.patch` so a scratchpad wipe cannot eat finished work, `fail`/`reset` handle a relaunch (reset returns the thread to pending, clears its prompt, and salvages then deletes the worktree and branch, refusing when the salvage failed or the branch holds unmerged commits), `merged --commit <sha>` records what already landed in the run branch and then retires the thread — worktree removed, `pd/<thread-id>` deleted, refusing (and exiting non-zero) while that branch is not an ancestor of HEAD, `status` prints the run at a glance and holds the gate shut on pending/running/failed threads (`-v` for per-thread detail, `--no-gate` for use in `&&` chains), `mirror` re-syncs the durable backup after a hand edit of the JSON, `restore` recovers the plan from that backup (refuses to clobber a newer hand-edited plan without `--force`). Every mutating command mirrors the plan into `<repo>/.git/parallel-dev/` — the scratchpad does NOT survive a process restart, the `.git` copy does. Use these instead of hand-editing the JSON; if you must hand-edit, run `mirror` right after.
- `scripts/run_codex.sh` — the only way to launch codex as a delegate, in either mode: default `--sandbox read-only` for review and second opinions, `--write --cwd <worktree>` for a code-editing thread (`--network` when its build must download dependencies, `--model`, `--out <file>`). It prints **only** the agent's final message on stdout — codex's own progress goes to stderr — so `run_codex.sh --write --cwd <wt> "$(cat prompt)" | plan_tool.py done <plan> <id>` is the whole handoff.
- `references/agent-prompt-template.md` — the template every agent prompt is built from. Read it when composing prompts; `plan_tool.py build` carries its non-negotiable blocks (file boundary, contracts preamble) so per-thread you author only the task body.

## Arguments

`/parallel-dev [N] [task description]`

- `N` — the total number of execution threads, resolved as described in "Quota
  authority and resolution" above.
- N threads = (N−1) concurrent agents + one thread for the main model. Example: the default N=5 → up to 4 agents in parallel, the fifth thread is done by the main model itself.
- An explicit `N` replaces the default; the default is not a ceiling.

## Step 1. Partitioning and the plan file

Before launching any agents, build a partitioning plan:

1. List every file the task will touch (both created and modified).
2. Group the work into threads with non-overlapping file sets. Pay special attention to "hub" files that almost every task edits: the version catalog and `build.gradle.kts`, DI modules, resources/strings, navigation, shared data models. Two pieces of work that edit the same hub belong to one thread; alternatively, defer all hub edits into `deferred_hub_edits` and let the main model apply them during the merge step.
3. Estimate the size of each thread (number of files and complexity of the edits).
4. **Write the plan to disk** as `parallel-dev-plan.json` in the session scratchpad directory (listed in your system prompt; fall back to `/tmp` if none). The plan file is the single source of truth for the whole run: unlike the conversation, it survives a context reset verbatim. Keep it updated for the entire run — statuses, agent summaries, actual files — through `plan_tool.py` (`launch`/`done`/`fail`), which also mirrors every write into `<repo>/.git/parallel-dev/`; after a process restart or scratchpad wipe, `plan_tool.py restore <plan>` brings the run back instead of you re-deriving it from memory.

Plan format (statuses: `pending` / `running` / `done` / `merged` / `failed`; `executor`: `main` / `agent`; `runner` — on `agent` threads only: omit it (or set `claude`) for an Agent tool subagent, set `codex` for a codex session; it is orchestrator bookkeeping that no script validates, while `executor: "agent"` is what keeps the thread inside `plan_tool.py`'s normal lifecycle; `worktree` and `branch` are filled in at launch time, `null` until then; the top-level `parallelism` block carries the quota resolved once at Step 1 and is read from there for the rest of the run, never re-derived; the top-level `base_branch` / `run_branch` are written by `start` — do not author them by hand):

```json
{
  "task": "one-line description of the overall task",
  "base_branch": null,
  "run_branch": null,
  "parallelism": { "total_threads": 5, "max_concurrent_delegates": 4 },
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
      "runner": "codex",
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
- The remaining threads go to agents, but no more than `parallelism.max_concurrent_delegates` run at once. If there are more independent threads than that, queue the extras: as soon as one agent finishes, launch the next one from the queue.
- Build each agent's prompt from `references/agent-prompt-template.md`. The mechanical way: put the template's shared halves once into the plan's `prompt_template` (`intro`, `tail`), give each thread only `task`, `files`, `contract_ids`, `verify` — and run `plan_tool.py build <plan>`; it splices in the file-boundary and contracts blocks itself. Two things the shared halves cannot carry, so they go into each thread's own fields: the worktree path (start `task` with the thread's `Your worktree is at <scratchpad>/wt-<thread-id>` line — the path is deterministic, so it is known before the worktree exists) and the Verification section (put it in `verify`, heading included, keeping the template's rule that finishing with a failing build or failing tests is not allowed). The template carries the non-negotiables — `using-agent-skills` bootstrap, the worktree confinement, the file boundary, the subagent ban that overrides any skill's fan-out suggestions, and the FILES CHANGED / SUMMARY / DEVIATIONS response format — do not strip them when filling it in.
- Launch each agent with a short bootstrap prompt pointing at the plan (`You are thread "<id>" of a parallel development run. Read <plan path>, find threads[] entry with id "<id>", and execute its "prompt" field as your complete and only instructions. Do not act on any other thread's prompt.`) rather than pasting the full prompt into the Agent call — the plan file is the single source of truth, and since `build` writes the finished prompts straight to disk, they never have to pass through the orchestrator's context at all.
- Launch every Agent tool agent on **Opus**: pass `model: "opus"` in each Agent tool call.
- **Choosing the runner.** By default a delegated thread goes to an Agent tool subagent (`runner` omitted or `claude`). Hand a thread to codex (`runner: "codex"`) when a second model's take is worth having on that piece, or when the Agent tool quota is already spent and codex slots are free. Codex is a code-editing executor, not an advisory one — under a validated plan it creates, edits, and deletes files in its own worktree exactly like a subagent does. Prefer a subagent for threads whose verification needs network access or caches outside the worktree (gradle, npm installs) — see the sandbox note in Step 5.
- **Codex prompts are authored, not assembled.** `build` splices in one shared `prompt_template.tail` for every thread, so a codex thread cannot get its own tail through `task` edits. Instead write the codex thread's `prompt` field directly (`build` leaves any thread that already has a `prompt` alone, and `kept` in its output lists them): take the template, drop **Before you start** (codex has no Skill tool), and reword the Agent-tool ban as "do not spawn sub-sessions and do not parallelize — execute this thread sequentially yourself". Everything else — worktree confinement, file boundary, contracts, verification, the FILES CHANGED / SUMMARY / DEVIATIONS response format — stays verbatim, and the thread's task must carry all project context since codex sees no conversation. Do not `--rebuild` a codex thread: that drops the hand-written prompt and re-assembles the Claude one; re-author it instead.

## Step 4. Checkpoint: present the final plan

At the very last moment before launching the parallel agents — when the plan file is written and validated and the agent prompts are stored in it — present the final plan to the user. This message must contain:

- a summary of the final plan (threads, file sets, who does what) so the user can sanity-check it;
- the resolved quota — `parallelism.total_threads` and `max_concurrent_delegates`, and how many delegates the first wave actually launches, with the reason if that is fewer;
- **a markdown link to the plan file** (absolute path) — mandatory, no exceptions: the plan file is the durable source of truth for the whole run.

Then launch the first wave immediately without re-deriving anything.

## Step 5. Launching agents

Immediately before the launch:

1. Re-validate the partition (the plan may have been edited): `check_partition.py check <plan>`.
2. **Ensure a clean baseline.** Worktrees branch off HEAD and do not see uncommitted changes in the main tree. If `git status` is not clean, commit the work in progress first; do not launch agents from a dirty tree.
3. **Open the run branch**: `plan_tool.py start <plan>`. It records the currently checked-out branch as the run's `base_branch` and creates + checks out `run_branch` (`pd/run-<digest of the plan path>`, or `--run-branch <name>`) in the main tree. This must happen **before the first `launch`**: thread worktrees fork from the current HEAD, so the run branch has to be the one they fork from. It refuses on a dirty tree or a detached HEAD, and re-running it after a restart just re-checks-out the branch. From here on, the main model commits its own thread on the run branch — the base branch stays untouched until Step 7.
4. **Worktrees are created by `plan_tool.py launch` itself** — with `--worktree` omitted it runs `git worktree add <plan-dir>/wt-<thread-id> -b pd/<thread-id>` off the repo's current HEAD (the run branch, after step 3), copies the plan's `worktree_seed_files` in (untracked per-machine config like `local.properties` — without it every gradle thread rediscovers the missing SDK path), and records path and branch into the plan. Pass `--worktree` only to adopt a pre-existing worktree. The main model does not get a worktree — it works in the main tree.

Launch all agents of a wave in a single message (parallel tool calls), each with its bootstrap prompt — Agent tool threads with `model: "opus"`, codex threads through `run_codex.sh` as shown below (its `--model` takes a codex model name, never `opus` — omit it unless you have a reason). Each agent works only inside its own worktree — the prompt states the worktree path as the repository root, and the file boundary keeps the eventual branch merges conflict-free. A fresh worktree also gives exact attribution: every change in it is that agent's work, no baseline bookkeeping needed.

**Order per thread: `launch` first, then spawn the agent.** `plan_tool.py launch <plan> <thread-id> <agent-id>` is what creates the worktree, and the agent's prompt sends it there on its first command — so the worktree must exist before the Agent call, never after it. (Pass the agent id you are about to use; it is bookkeeping, not a handle the tool resolves.)

**Launching a codex thread.** Same order — `launch` first (agent id `codex-<thread-id>`), then one Bash call to `scripts/run_codex.sh`, which is the only sanctioned way to start codex:

```
scripts/run_codex.sh --write --cwd <worktree from the plan> [--network] "<the thread's prompt>"
```

`--write` selects the code-editing sandbox (`workspace-write`); without it the script stays read-only, which is what plan-free consultations use. `--cwd` is mandatory in `--write` mode and must be that thread's worktree — it is what makes the sandbox coincide with the thread's isolation. Pass the prompt as the argument (or `-` to read it from stdin, e.g. from the plan's `prompt` field). Run the call in the background if the wave is large, but never poll it in a loop.

**Sandbox vs. verification.** `workspace-write` makes `--cwd` writable (plus temp dirs), and the sandbox has no network unless `--network` is passed. A thread whose verification downloads dependencies or writes a cache outside the worktree — gradle into `~/.gradle`, npm into `~/.npm` — fails its mandatory build under the defaults. Decide before launching: either pass `--network` and add an `export GRADLE_USER_HOME=…` / `npm_config_cache=…` line pointing at a temp dir to that thread's `verify` block (a temp dir, not a path inside the worktree, where the cache would show up as untracked files and trip the boundary audit), or give that thread to an Agent tool subagent instead. If it only turns out mid-run, the thread reports the blocked verification under DEVIATIONS and the main model builds that thread's code itself before merging — an unverified thread must never be merged silently.

Repository edits stay in the worktree by the combination of `--cwd`, the sandbox, and the prompt's file boundary — audit the worktree before merging exactly as for any other thread (`check_partition.py audit --thread`). Codex leaves its changes uncommitted like the subagents, and the script prints its final message and nothing else, so the handoff is a plain pipe into `plan_tool.py done <plan> <thread-id>` (or `--out <file>` if you want the report on disk too). The run is one-shot: there is no mid-thread reply channel here, so a thread that stops with a question or unusable work goes through `fail` → `reset` → relaunch with the gap closed in its prompt. One difference from the relaunch sequence below: `reset` clears the thread's prompt, so a codex thread is re-authored by hand into `prompt` again and then run through plain `build` — never `build --rebuild`, which would assemble the Claude-tail version.

While the agents work, the main model executes its own thread. Do not poll the agents in a waiting loop — the completion notification arrives on its own. When an agent finishes, pipe its final report into `plan_tool.py done <plan> <thread-id>` (stdin or `--report <file>`) — it parses FILES CHANGED / SUMMARY / DEVIATIONS into the plan itself and snapshots the worktree's uncommitted diff to `.git/parallel-dev/patches/<slot>/<thread-id>.patch`, the insurance that lets a wiped scratchpad be recovered with `git apply`. A report that yields no FILES CHANGED entries — missing, empty, or unparseable — makes `done` fail loudly instead of recording an unverifiable thread: fix the report and re-run, or use `--allow-unparsed --summary <text>` and review that thread's diff by hand, since its boundary check is then skipped. If the agent was cancelled or returned unusable work: `plan_tool.py fail <plan> <thread-id> --note <why>`, then for a relaunch `plan_tool.py reset <plan> <thread-id>` (this salvages a patch and then deletes the worktree and the `pd/<thread-id>` branch, so the new agent starts clean) → edit the thread's `task` if needed → `build --rebuild <thread-id>` → `launch`. `reset` refuses to delete when the snapshot failed or when the branch holds commits that are merged nowhere — the patch covers uncommitted work only. Merge or cherry-pick those commits first; `reset --force` throws them away. Then, if the queue is not empty, launch the next thread. `plan_tool.py status <plan>` shows the run at a glance and exits non-zero while anything is pending, running, or failed (`--no-gate` when that exit code would break a `&&` chain, `-v` for per-thread detail).

### Resource cost of parallel builds

Each worktree pays for its own cold build: `build/` directories are per-worktree and must not be shared. The user-level Gradle cache (`~/.gradle`) is shared between worktrees automatically and that is safe — leave it alone. Still, N concurrent cold builds are expensive in CPU, memory, and wall-clock time: factor this into Step 2 when deciding how many threads are worth it, and prefer fewer, larger threads on a resource-constrained machine.

## Step 6. Merge and verification

Once `plan_tool.py status <plan>` shows every thread finished (exit code 0 — `failed` threads hold the gate shut too, and must be relaunched or dropped from the plan first), the main model:

1. Commits its own thread in the main tree, i.e. onto the run branch (a merge over uncommitted changes is fragile even with disjoint file sets — don't rely on it), and records it like any other thread: `plan_tool.py merged <plan> <main-thread-id> --commit $(git rev-parse HEAD)`. The main thread has no branch of its own, so nothing is retired here — but Step 7 requires every thread to be `merged`.
2. Then, for each agent worktree in turn:
   1. Runs the boundary audit against that worktree: `check_partition.py audit <plan> --repo <worktree> --thread <thread-id>`. **`--thread` is not optional here**: it narrows the allowed set to that one thread, and without it the allowed set is the union of every thread — under which an agent that wandered into a neighbouring thread's file passes the audit clean, which is exactly the failure the partition invariant exists to prevent. Agents leave their changes uncommitted, so the status-based audit sees exactly this agent's work, and the script's "no baseline" warning is expected — a fresh worktree needs none. Investigate every violation before proceeding.
   2. Reviews the agent's diff (`git diff` in the worktree): conformance to the task, the contracts, and the project style; reconciles any deviations the agent flagged.
   3. Commits the reviewed changes onto the thread branch (inside the worktree), then merges it into the run branch from the main tree: `git merge pd/<thread-id>`. Disjoint file sets make this merge conflict-free; a conflict here means the audit missed something — stop and investigate.
   4. Records the merge and takes the thread's scaffolding down in one step: `plan_tool.py merged <plan> <thread-id> --commit $(git rev-parse HEAD)`. Besides recording (so a recovery never re-derives the merge from the git log), this removes the worktree and deletes `pd/<thread-id>` — **a thread branch does not outlive its merge**. The deletion is gated on that branch being an ancestor of HEAD, so the command exits non-zero and keeps everything standing if the merge above did not actually happen; do not paper over that with `--force`, fix the merge. Only when you deliberately need the worktree a while longer (a build still running in it) pass `--keep-worktree` and re-run `merged` without it afterwards.
3. Applies the deferred "hub" edits (DI registration, strings/resources, navigation, gradle) on the run branch, and commits them — Step 7 needs a clean tree.
4. Runs the full build and the test suite in the main tree.

## Step 7. Closing the run

The work is now complete on the run branch and every thread branch is gone. Close the run with one command, from the main tree, with a clean `git status`:

```
python3 .claude/skills/parallel-dev/scripts/plan_tool.py finish <plan>
```

It checks that every thread is `merged`, retires anything still standing, checks out the base branch, merges the run branch into it, deletes the run branch, prunes worktrees, and warns about any `pd/*` branch that survived. It refuses rather than improvises: an unmerged thread, a dirty tree, or a HEAD that is not the run branch each stop it with an explanation. A merge conflict against the base branch (it moved under the run) is aborted, leaving the base branch untouched and the run branch intact — resolve it by hand, then re-run. Do not delete the run branch yourself before `finish` has merged it.

Then verify the end state and report:

1. `git rev-parse --abbrev-ref HEAD` — must equal the plan's `base_branch`, i.e. the branch the run was invoked from: a run ends where it started, with the work merged into that branch.
2. `git branch --list 'pd/*'` — must print nothing, and `git worktree list` must show only the main tree. **A run that leaves any parallel-dev branch or worktree behind is not finished.**
3. Reports to the user: how the work was split into threads, what each one did, audit results, the build/test results, and the branch the work landed on.

## If you are a subagent yourself

If these instructions are being read inside a subagent — do not apply them: do the work sequentially yourself. Recursive parallelization is forbidden.
