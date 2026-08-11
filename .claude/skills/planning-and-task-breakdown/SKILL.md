---
name: planning-and-task-breakdown
description: Breaks work into ordered tasks. Use when a spec or clear requirements exist and need decomposing into implementable units, when a task feels too large to start, or when work will be parallelized. Not for single-file changes with obvious scope, or when the spec already contains well-defined tasks.
---

# Planning and Task Breakdown

Decompose work into small, verifiable tasks with explicit acceptance criteria. Each task should be implementable, testable, and verifiable in one focused session — that's the difference between reliable completion and a tangled mess.

## Process

1. **Plan read-only.** Read the spec and relevant code; identify existing patterns, dependencies, risks. The output is a plan, not code.
2. **Map the dependency graph** (schema → types → endpoints → client → UI; migrations feed everything) to learn what must precede what.
3. **Slice vertically** — tasks are complete feature paths (data + logic + UI for one capability), never layer-tasks like "all the schema, then all the endpoints". The dependency graph orders *within and between* slices (shared prerequisites and contracts land before the slices that consume them); it does not turn layers into tasks. Slicing strategies (vertical / contract-first / risk-first) are owned by incremental-implementation.
4. **Write each task** with: one-paragraph description, testable acceptance criteria, a concrete verification step (command + expected result, manual check if needed), dependencies, files likely touched, size estimate.
5. **Order and checkpoint.** Dependencies satisfied; each task leaves the system working; high-risk tasks early (fail fast); an explicit checkpoint every 2–3 tasks (tests pass, build clean, core flow works, human reviews before proceeding).

## Sizing

S (1–2 files, one endpoint/component) and M (3–5 files, one feature slice) are the sweet spot. Break a task down further when: it would exceed one focused session (~2 hours), its acceptance criteria don't fit in 3 bullets, it spans two independent subsystems, or its title contains "and" — that's two tasks.

## Plan document shape

Overview paragraph → key architecture decisions with rationale → phased task list with checkpoints between phases → risks with impact and mitigation → open questions needing human input. Written plans survive session boundaries and compaction; in-head plans don't.

## Parallelization

Safe in parallel: independent feature slices, tests for already-landed features, docs. Strictly sequential: migrations, shared-state changes, dependency chains. Needs coordination: anything sharing an API contract — define the contract first, then parallelize against it.

## Verification

Every task has acceptance criteria and a verification step; dependencies ordered; no task beyond ~5 files; checkpoints between phases. Get the human's review of the plan when it contains unresolved consequential choices, when they asked to review, or when the workflow requires approval — otherwise a clear plan for a clear request can proceed.
