---
name: incremental-implementation
description: Delivers changes incrementally. Use when implementing a feature or change that spans multiple files, or when about to write a large amount of code in one pass. Not for single-file, single-function changes whose scope is already minimal.
---

# Incremental Implementation

Build in thin vertical slices: implement one piece, test it, verify it, commit it, expand. Each increment leaves the system working. This is the execution discipline that makes large features manageable — and that localizes bugs to the slice that introduced them.

## The cycle

Implement the smallest complete piece → run tests (write one if none exists) → verify (build, manual check where relevant) → make it a save point → next slice. Never leave the codebase broken between slices. "Save point" means commit when the user or project workflow authorizes committing; otherwise leave the increment verified and commit-ready — don't commit on your own initiative.

## Slicing strategies

- **Vertical (default):** one complete path through the stack per slice — "create a task: DB + API + minimal UI" — so every slice delivers working end-to-end behavior.
- **Contract-first:** when frontend and backend proceed in parallel — slice 0 defines the typed contract, then each side implements against it (backend + API tests; frontend + mocks), then integrate.
- **Risk-first:** prove the riskiest assumption first ("the WebSocket connection works") before building on it — a failed slice 1 is cheap; the same discovery after slices 2–3 is not.

## Rules

- **Simplicity first.** Before coding: what's the simplest thing that could work? After: could this be fewer lines; do the abstractions earn their keep; am I building for hypothetical futures? Three similar lines beat a premature abstraction — generalize at the third use case, not the first. Naive-and-correct first; optimize after tests prove correctness.
- **Scope discipline.** Touch only what the task requires. No adjacent "cleanup", no modernizing files you're only reading, no removing comments you don't understand, no unrequested features. Things worth improving outside scope get *noted* ("noticed but not touching: …") and offered as separate tasks — not fixed on the spot.
- **One logical change per increment** — a new component, a refactor, and a config change are three increments, not one.
- **Feature flags for incomplete features** so increments can merge to main without exposing unfinished work.
- **Safe defaults** — new behavior ships opt-in and conservative (`notify ?? false`), not opt-out.
- **Rollback-friendly** — prefer additive changes; keep modifications focused; migrations get down-paths; don't delete and replace in the same commit.

## Verification per increment

Tests, build, typecheck, lint green; the new functionality demonstrated; the increment committed or left cleanly commit-ready per the workflow. Run each command after changes that could affect it — but don't re-run an unchanged, already-green command for reassurance; a second identical run adds no information. When all slices land: full suite passes, the feature works end-to-end as specified, and no half-finished stragglers remain outside the final state.
