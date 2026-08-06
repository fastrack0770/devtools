---
name: code-simplification
description: Simplifies code for clarity without changing behavior. Use when working code is harder to read, maintain, or extend than it should be, or when review flags accumulated complexity. Not for code you don't yet understand, performance-critical paths where the simpler version is slower, or modules about to be rewritten.
---

# Code Simplification

Reduce complexity while preserving exact behavior. The goal is not fewer lines — it's faster comprehension. Every change must pass one test: *would a new team member understand this faster than the original?*

## Principles

1. **Preserve behavior exactly.** Same outputs, side effects, ordering, and error behavior for every input; all existing tests pass unmodified. If unsure a change preserves behavior, don't make it. Needing to modify a test to keep it green means you changed behavior, not expression.
2. **Follow project conventions.** Simplification makes code more consistent with its codebase, not with your preferences. Check CLAUDE.md and neighboring code first — a "cleaner" style that breaks consistency is churn, not simplification.
3. **Clarity over cleverness.** Explicit beats compact when compact needs a mental pause: a nested ternary chain loses to an if-chain; a chained reduce with inline spread logic loses to a named loop.
4. **Balance — over-simplification is a real failure mode.** Don't inline a helper that gave a concept its name; don't merge two simple functions into one complex one; don't strip abstractions that exist for testability or extension; don't optimize for line count.
5. **Scope to what changed.** Simplify recently modified code by default; drive-by refactors of unrelated code create noisy diffs and unearned risk.

## Process

**1. Understand first (Chesterton's Fence).** Before touching anything: what is this code's responsibility, who calls it, what are the edge cases, why might it be written this way (performance? platform quirk? — check git blame)? If you can't answer, you're not ready to simplify.

**2. Scan for concrete signals**, not vague smells:

- *Structure:* 3+ nesting levels → guard clauses; 50+-line functions → split; nested ternaries → if/switch/lookup; boolean flag params → options object or separate functions; the same `if`-condition repeated → named predicate.
- *Naming:* `data`/`result`/`temp` → name the content; misleading names (a `get` that mutates) → rename to the truth; "what"-comments (`// increment counter`) → delete; "why"-comments (`// retry: API flaky under load`) → keep, they carry intent code can't.
- *Redundancy:* duplicated 5+-line blocks → extract; dead code and commented-out blocks → remove after confirming dead; wrappers adding nothing → inline; one-strategy strategy patterns → the direct call; speculative abstractions with zero current users → remove, re-add when needed.

**3. Apply incrementally.** One simplification → run tests → commit or move on; on failure, revert that one change. Never batch untested simplifications — you won't know which one broke things. Refactoring ships separately from feature/bugfix changes. If a refactor would touch 500+ lines, automate it (codemod/AST transform) rather than hand-editing.

**4. Evaluate the whole.** Is the result genuinely easier to understand, consistent with the codebase, and cleanly reviewable? If not, revert — not every simplification attempt succeeds, and reverting is cheaper than defending a sideways diff.

## Verification

Tests pass unmodified; build and lint clean; diff contains only the intended simplifications; no error handling weakened; no dead code left behind (unused imports, unreachable branches); the change would read as a net improvement to a reviewer.
