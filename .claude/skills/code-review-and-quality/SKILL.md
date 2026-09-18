---
name: code-review-and-quality
description: Conducts multi-axis code review. Use when a completed change is ready for pre-merge review, or when evaluating code produced by another agent or human. Not for in-progress work (finish the slice first), pure formatting diffs, or generated lockfiles.
---

# Code Review and Quality

Review across five quality axes plus a separate spec axis before merge. Approve when the change definitely improves overall code health, even if it is not perfect; better is the bar.

## The five quality axes

1. **Correctness** — intended behavior, edge cases and error paths; tests prove the right thing; no off-by-ones, races, or inconsistent state.
2. **Readability & simplicity** — meaningful names, straightforward logic, earned abstractions, no dead artifacts or unsolicited compatibility shims. Load `references/smell-baseline.md` when walking a diff larger than a few hunks.
3. **Architecture** — existing patterns or justified departures, clean boundaries, one-way dependencies, fitting abstraction levels. Load `references/smell-baseline.md` when walking a diff larger than a few hunks.
4. **Security** — validated input, absent secrets, checked authorization, injection resistance, external data treated as untrusted. For a deep dive, use the security-and-hardening checklist.
5. **Performance** — no N+1s, unbounded fetches, missing pagination, or hot-path waste. For a deep dive, use the performance-optimization checklist.

## Spec axis

Find the originating spec in this order:

1. The active OpenSpec change: `openspec/changes/<name>/proposal.md`, `specs/`, and `tasks.md`.
2. A path the user passed.
3. Issue references in `git log` commit messages.
4. A relevant spec under `docs/`.
5. If none exists, report **no spec available**.

Report separately: requirements missing or partial; behavior not asked for (scope creep); and requirements that look implemented but are wrong. Quote the spec line for every finding.

The axis stays separate because standards can pass while the spec fails. The spec can also pass while standards fail, and both outcomes must remain visible rather than being merged or reranked.

## Process

1. **Pin the fixed point.** Use the ref the user names, or the branch's merge-base with `main`. Resolve it with `git rev-parse <ref>`, inspect `git diff <ref>...HEAD` (three-dot), and list commits with `git log <ref>..HEAD --oneline`. Fail early on a bad ref or empty diff.
2. **Understand intent and locate the spec** using the order above.
3. **Read tests before implementation** to expose intended behavior and coverage gaps.
4. **Walk the diff** with the five quality axes.
5. **Run the spec axis separately.** If two reviewers cover standards and spec, run them sequentially or Call the Skill tool with "parallel-dev" first and stay within its quota.
6. **Label each quality finding with severity:**

| Prefix | Meaning |
|--------|---------|
| *(no prefix)* | Required before merge |
| **Critical:** | Blocks merge: security, data loss, broken functionality |
| **Nit:** | Optional style or formatting preference |
| **Consider:** | Suggestion worth weighing, not required |
| **FYI:** | Context only, no action |

7. **Check the verification story:** commands and results, screenshots for UI, and before/after evidence where useful.

Done when the fixed point and non-empty diff are verified, both available axes are reported without cross-axis reranking, and the verification evidence is assessed.

## Delegated review passes

A delegate handed a review — codex, or an Agent tool subagent — reads until its budget ends, and what it reads is decided entirely by the prompt. Two failures dominate: it reviews code outside the range, and it reads whole files where the diff hunks would have answered the question. Before launching one, load `references/delegate-prompt.md` and build the prompt from it. The contract in short: pass the merge-base SHA rather than a branch name, paste the `git diff --numstat` file list as the set under review and its priority order, give a diff-first reading method with a capped allowance for numbered slices around a hunk, quote the repository rules the change could touch instead of pointing at the rules file, and set a file budget, a stop rule, and a coverage line to report on stopping.

Findings come back as a draft: confirm each Critical against the code, and carry the delegate's unexamined files into the review as a coverage gap rather than as clean.

## Change sizing

Small focused changes review better: ~100 lines is ideal, ~300 acceptable for one logical change, ~1000 needs splitting. Refactoring and behavior change are separate changes. For mechanical renames, deletions, or generated code, review intent rather than every line.

## Review honesty

- Ground approval in evidence; quantify issues when possible.
- State real issues directly, propose alternatives, accept informed overrides, and comment on code rather than people.
- Require cleanup before merge or an explicit owned follow-up.
- Resolve disagreements by technical facts, style guide, engineering principles, then codebase consistency.

## Adjacent duties

- **Dead code:** list newly orphaned code and ask before deleting it.
- **New dependencies:** check whether the stack already covers the need, plus size, maintenance, vulnerabilities, and license.
- **Change description:** short imperative first line; body explains what and why with context links.

## Verdict

Approve when all Critical and required quality findings are resolved, spec-axis findings are explicitly addressed, tests and build pass, and the verification story is documented. Otherwise request changes with the severity-labeled quality list and the separate spec report.

## Verification

Fixed point resolves and the three-dot diff is non-empty; five quality axes reviewed; spec axis reported separately or says "no spec available"; any delegated pass launched on a merge-base SHA, an explicit file list, a budget and a stop rule; findings cite evidence; tests, build, and verification story assessed before the verdict.
