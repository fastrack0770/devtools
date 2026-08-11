---
name: code-review-and-quality
description: Conducts multi-axis code review. Use when a completed change is ready for pre-merge review, or when evaluating code produced by another agent or human. Not for in-progress work (finish the slice first), pure formatting diffs, or generated lockfiles.
---

# Code Review and Quality

Review across five axes before merge: correctness, readability, architecture, security, performance.

**The approval standard:** approve when the change definitely improves overall code health, even if it isn't perfect. Don't block a change for not being how you would have written it. Perfect is not the bar; better is.

## The five axes

1. **Correctness** — matches the spec; edge cases (null/empty/boundary) and error paths handled; tests exist and actually test the right things; no off-by-ones, races, or state inconsistencies.
2. **Readability & simplicity** — understandable without the author; names carry meaning; no clever tricks that need decoding; abstractions earn their complexity (don't generalize before the third use case); no dead-code artifacts or backwards-compat shims nobody asked for.
3. **Architecture** — follows existing patterns or justifies a new one; clean module boundaries; dependencies flow in one direction; abstraction level fits the problem.
4. **Security** — input validated, secrets absent, auth checked, injections impossible, external data treated as untrusted. Deep dive: the security-and-hardening skill and its checklist at `.claude/skills/security-and-hardening/references/security-checklist.md`.
5. **Performance** — no N+1s, unbounded fetches, missing pagination, or hot-path waste. Deep dive: `.claude/skills/performance-optimization/references/performance-checklist.md`.

## Process

1. **Understand intent first** — what is this change for, per which spec or task?
2. **Read the tests before the implementation** — they reveal intended behavior and coverage gaps.
3. **Walk the diff with the five axes.**
4. **Label every finding with severity** so the author knows what's binding:

| Prefix | Meaning |
|--------|---------|
| *(no prefix)* | Required before merge |
| **Critical:** | Blocks merge — security, data loss, broken functionality |
| **Nit:** | Optional — style/format preference |
| **Consider:** | Suggestion worth weighing, not required |
| **FYI:** | Context only, no action |

5. **Check the verification story** — what was run, did it pass, screenshots for UI, before/after where relevant.

## Change sizing

Small focused changes review better: ~100 lines is ideal, ~300 acceptable for one logical change, ~1000 needs splitting (stack sequential changes, split by layer, or slice the feature vertically). Refactoring and behavior change are two separate changes. Exceptions: mechanical renames, deletions, generated code — review the intent, not every line.

## Review honesty

- No rubber-stamping — "LGTM" without evidence of review helps no one.
- Don't soften real issues; quantify when possible ("adds ~50ms per list item" beats "could be slow").
- Push back on approaches with clear problems, propose an alternative, and accept an informed override gracefully. Comment on the code, not the person.
- Don't accept "I'll clean it up later" — require cleanup pre-merge or an explicitly filed, self-assigned follow-up.
- Disagreements resolve in order: technical facts → style guide → engineering principles → codebase consistency.

## Adjacent duties

- **Dead code:** after refactors, list newly orphaned code explicitly and ask before deleting — don't leave it, don't silently remove it.
- **New dependencies:** does the existing stack cover it; size, maintenance, vulnerabilities, license. Prefer stdlib and existing utilities — every dependency is a liability.
- **Change description:** first line short, imperative, standalone; body says what and why with links to context. "Fix bug" is not a description.

## Verdict

Approve when all Critical/required findings are resolved, tests and build pass, and the verification story is documented. Otherwise request changes with the severity-labeled list.
