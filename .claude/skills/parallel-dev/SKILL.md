---
name: parallel-dev
description: Parallel development orchestration — splits implementation work into threads with non-overlapping file sets, hands some threads to subagents while the main model takes the largest thread itself. Invoke on /parallel-dev, and also whenever the user asks to "parallelize", "split the work", "use multiple agents", "fan out the work", or when implementing a large change with independent groups of files (several screens, layers, or modules at once). Accepts an optional argument — the number of threads (default 2, one agent + the main model).
---

# Parallel development

Rules for dividing implementation work between subagents (Agent tool) and the main model. The goal is speedup without conflicting edits, so the core invariant is: **the file sets of the threads must not overlap**.

## Arguments

`/parallel-dev [N] [task description]`

- `N` — number of threads, default **2**.
- N threads = (N−1) concurrent agents + one thread for the main model. Example: N=5 → up to 4 agents in parallel, the fifth thread is done by the main model itself.

## Step 1. Partitioning

Before launching any agents, build a partitioning plan:

1. List every file the task will touch (both created and modified).
2. Group the work into threads with non-overlapping file sets. Pay special attention to "hub" files that almost every task edits: the version catalog and `build.gradle.kts`, DI modules, resources/strings, navigation, shared data models. Two pieces of work that edit the same hub belong to one thread; alternatively, defer all hub edits and let the main model apply them during the merge step.
3. Estimate the size of each thread (number of files and complexity of the edits).

## Step 2. Decision: parallelize or not

Invoking the skill is not an obligation to parallelize. Check in order:

- **No non-overlapping partition exists** (all the work is coupled through shared files) → the main model does everything itself, sequentially. Tell the user that parallelization is impossible and name the overlapping files.
- **A thread is too small** — rule of thumb: one or two files with minor edits, a few minutes of work → do not create an agent for it, even if it is independent: spawning, context handoff, and reviewing the agent will eat the entire gain. The main model does such pieces itself before or after its own main thread.
- **≥2 substantial independent threads remain** → parallelize.

## Step 3. Assignment

- By default the main model takes the thread with the **largest amount of work**: it has the full context of the conversation and the project, and the biggest (usually the riskiest) piece should live where the context is richest.
- The remaining threads go to agents, but no more than (N−1) agents run at once. If there are more independent threads than that, queue the extras: as soon as one agent finishes, launch the next one from the queue.

## Step 4. Checkpoint: ask the user to run /compact

At the very last moment before launching the parallel agents — when the partitioning plan, the assignment, and the agent prompts are ready — stop and end your turn. Explicitly ask the user to run `/compact` and to send a follow-up message when it is done. `/compact` is a user-side command; you cannot run it yourself, so you must pause and wait. Rationale: the launch starts a long autonomous phase (agents working + merge + build), and compacting right before it frees the context for that phase instead of wasting it on the already-digested planning discussion.

Present the final plan (threads, file sets, who does what) in that same message so the user can sanity-check it before compaction. After the user returns, launch the agents immediately without re-deriving the plan.

## Step 5. Launching agents

Launch all agents of a wave in a single message (parallel tool calls). Agents work in the shared working tree — this is safe precisely because the file sets do not overlap; make sure the restriction is explicit. Each agent's prompt is self-contained (the agent cannot see the conversation) and must include:

- the task, context, and completion criteria;
- an instruction to begin by invoking the `using-agent-skills` skill (via the Skill tool), so the agent discovers and applies whatever project skills are relevant to its thread — the agent does not see this conversation and would otherwise skip skills the main model benefits from;
- **the exact list of files it may create/modify, and an explicit ban on touching anything else** (especially gradle files and shared resources);
- an explicit ban on spawning subagents: "Do not call the Agent tool for any purpose and do not parallelize the work — execute your thread sequentially yourself" (this also overrides anything a skill or instruction inside the agent's context may suggest about fanning out work);
- how to verify itself: build/test commands (in this project, run `export JAVA_HOME=/home/user/dev-tools/jdk-17.0.19+10` before gradle);
- the response format: list of modified files + a brief summary of the decisions made (needed for the merge step).

While the agents work, the main model executes its own thread. Do not poll the agents in a waiting loop — the completion notification arrives on its own; at that moment, if the queue is not empty, launch the next agent.

## Step 6. Merge and verification

Once all threads are finished, the main model:

1. Reviews each agent's diff (`git diff` over its files): conformance to the task, the project style, and the file boundaries.
2. Applies the deferred "hub" edits (DI registration, strings/resources, navigation, gradle).
3. Runs the full build and the test suite.
4. Reports to the user: how the work was split into threads, what each one did, and the build/test results.

## If you are a subagent yourself

If these instructions are being read inside a subagent — do not apply them: do the work sequentially yourself. Recursive parallelization is forbidden.
