---
name: planning-and-task-breakdown
description: Breaks work into ordered tasks. Use when a spec or clear requirements exist and need decomposing into implementable units, when a task feels too large to start, or when work will be parallelized. Not for single-file changes with obvious scope, or when the spec already contains well-defined tasks.
---

# Planning and Task Breakdown

Decompose work into small, verifiable tasks with explicit acceptance criteria. Each task should fit one fresh context window of an agent and declare what blocks it.

## Process

1. **Plan read-only.** Read the spec and relevant code; identify existing patterns, dependencies, risks. Look for prefactoring first: make the change easy, then make the easy change. The output is a plan, not code.
2. **Map the dependency graph** (schema → types → endpoints → client → UI; migrations feed everything) to learn what must precede what.
3. **Tracer bullet: slice vertically** — a narrow but complete path through every layer, demoable or verifiable on its own. Tasks are complete feature paths (data + logic + UI for one capability), never layer-tasks like "all the schema, then all the endpoints". The dependency graph orders within and between slices; it does not turn layers into tasks.
4. **Write each task** with: one-paragraph description, testable acceptance criteria, a concrete verification step (command + expected result, manual check if needed), **Blocked by** (the tasks that gate it, or "none: can start immediately"), files likely touched, size estimate.
5. **Order and checkpoint.** Dependencies satisfied; each task leaves the system working; high-risk tasks early (fail fast); an explicit checkpoint every 2–3 tasks (tests pass, build clean, core flow works, human reviews before proceeding).

## Sizing

S (1–2 files, one endpoint/component) and M (3–5 files, one feature slice) are the sweet spot. Break a task down further when it does not fit one fresh context window of an agent, its acceptance criteria do not fit in 3 bullets, it spans two independent subsystems, or its title contains "and" — that is two tasks.

**Wide refactor exception.** When one mechanical change has a blast radius too broad for a green tracer bullet, use expand–migrate–contract: expand by adding the new form beside the old; migrate callers in batches sized by blast radius, each blocked by expand; contract by deleting the old form, blocked by every migration batch. Keep each batch green where possible; if that is impossible, preserve the sequence and add a final integrate-and-verify task.

## Plan document shape

Overview paragraph → key architecture decisions with rationale → phased task list with checkpoints between phases → risks with impact and mitigation → open questions needing human input. In this repo, an OpenSpec change's task list is `tasks.md`, so put these fields there. Written plans survive session boundaries and compaction; in-head plans don't.

## Parallelization

The **frontier** is the set of tasks whose blockers are all done. Work the frontier next; Call the Skill tool with "parallel-dev" when multiple frontier tasks may run concurrently. Migrations, shared-state changes, and dependency chains remain sequential; shared API contracts land before parallel consumers.

## Verification

Every task has acceptance criteria, a verification step, and a Blocked by field; dependencies are ordered; no ordinary task exceeds ~5 files or one fresh agent context; checkpoints separate phases. Get the human's review of the plan when it contains unresolved consequential choices, when they asked to review, or when the workflow requires approval — otherwise a clear plan for a clear request can proceed.
