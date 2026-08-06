---
name: spec-driven-development
description: Creates specs before coding. Use when starting a project, feature, or significant change with no specification yet — especially when requirements are ambiguous or exist only as a vague idea. Not for single-line fixes, typos, or changes whose requirements are unambiguous and self-contained.
---

# Spec-Driven Development

## Overview

Write a structured specification before writing any code. The spec is the shared source of truth between you and the human engineer — it defines what we're building, why, and how we'll know it's done. Code without a spec is guessing.

**In this repository the spec workflow is OpenSpec.** This skill defines the principles; the mechanics live elsewhere:

- **Artifacts (proposal / design / specs / tasks)** → `openspec-propose` (or `openspec-explore` first, if the idea is still vague). Do not invent a parallel spec format — OpenSpec change artifacts *are* the spec.
- **Task breakdown** → `planning-and-task-breakdown` (task template, sizing, dependency ordering, checkpoints).
- **Implementation** → `openspec-apply-change`, following `incremental-implementation` and `test-driven-development`.

## When to Use

- Starting a new project or feature
- Requirements are ambiguous or incomplete
- The change touches multiple files or modules
- You're about to make an architectural decision
- The task would take more than 30 minutes to implement

**When NOT to use:** Single-line fixes, typo corrections, or changes where requirements are unambiguous and self-contained.

## Principles

### Surface assumptions before writing anything

List what you're assuming and get it corrected *before* the spec exists:

```
ASSUMPTIONS I'M MAKING:
1. [assumption about requirements]
2. [assumption about architecture or stack]
3. [assumption about scope]
→ Correct me now or I'll proceed with these.
```

Don't silently fill in ambiguous requirements — assumptions are the most dangerous form of misunderstanding.

### Reframe instructions as success criteria

Translate vague requirements into concrete, testable conditions:

```
REQUIREMENT: "Make sync faster"

REFRAMED SUCCESS CRITERIA:
- Delta sync completes in < 5s on a 200-event calendar
- Full re-sync is triggered only when ctag changes
→ Are these the right targets?
```

This lets you loop and problem-solve toward a clear goal instead of guessing what "faster" means.

### A complete spec answers six questions

Whatever the artifact format, it should cover: **Objective** (what/why/who, success criteria), **Tech stack**, **Commands** (full build/test/lint commands), **Project structure**, **Testing strategy**, **Boundaries** (always do / ask first / never do). In an OpenSpec change these map onto proposal.md + design.md + specs; repo-wide items (commands, structure, boundaries) belong in CLAUDE.md, not per-change.

### The spec is a living document

Update it when decisions or scope change — spec first, then implement. In OpenSpec terms: update the change artifacts mid-flight, and sync delta specs to main specs (`openspec-sync-specs`) when the change lands.

## Verification

Before proceeding to implementation, confirm:

- [ ] Assumptions were surfaced — and confirmed by the human where consequential
- [ ] Success criteria are specific and testable
- [ ] The spec exists as OpenSpec change artifacts (not only in conversation)
- [ ] The human approved the proposal when it involves unresolved consequential choices or they asked to review; otherwise proceed and keep the artifacts available for review
