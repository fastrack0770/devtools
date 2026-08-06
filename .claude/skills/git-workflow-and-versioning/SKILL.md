---
name: git-workflow-and-versioning
description: Structures git workflow practices. Use when deciding how to commit, branch, split, or sequence changes — organizing work into atomic commits, naming branches, handling parallel streams, or cleaning up history. Not a gate on every edit; invoke at commit/branch decision points, not for each file change.
---

# Git Workflow and Versioning

Git is the safety net: commits are save points, branches are sandboxes, history is documentation. With agents generating code fast, commit discipline is what keeps changes reviewable and reversible.

## Trunk-based development (recommended default)

Keep `main` always deployable; work in feature branches that merge back within 1–3 days. Every day a branch lives it accumulates merge risk — prefer feature flags over long-lived branches for incomplete work; release branches are fine for stabilization. Teams on gitflow can keep their model — the commit discipline below matters more than the branching topology.

## Commit discipline

- **Commit early, commit often.** Each verified increment is a save point: implement → test → commit. If the next change breaks, revert just that increment (`git revert`, or discard only the affected files) — small commits make recovery surgical. `git reset --hard` also destroys unrelated uncommitted work; use it only when the working tree is confirmed clean of anything worth keeping.
- **Atomic commits.** One logical change per commit. "Add task feature, fix sidebar, update deps" is three commits wearing a trench coat.
- **Messages explain why**, in the conventional format `<type>: <short imperative description>` (+ optional body for reasoning). Types: feat, fix, refactor, test, docs, chore. "update auth.ts" tells history nothing.
- **Separate concerns.** Formatting apart from behavior; refactors apart from features — mixed changes are harder to review, revert, and bisect. Tiny cleanups (a rename) may ride along at reviewer discretion.
- **Size:** ~100 lines reviews easily, ~300 is fine for one logical change, ~1000 gets split (strategies in code-review-and-quality).

## Branches and worktrees

Branch names: `feature/…`, `fix/…`, `chore/…`, `refactor/…`. Branch from main, delete after merge. For genuinely parallel streams, `git worktree add ../project-feature-a feature/a` gives each stream its own directory — no branch-switching, failed experiments delete cleanly, changes stay isolated until merged.

## Change summaries

After a modification, summarize in three sections: **changes made** (file: what), **intentionally not touched** (adjacent issues left alone — this documents scope discipline), **potential concerns** (strictness choices, new dependencies, things to confirm). The "didn't touch" list catches wrong assumptions early and shows reviewers the change's true boundary.

## Pre-commit hygiene

Review `git diff --staged` before committing; scan it for secrets; run tests/lint/typecheck. Automate the mechanical parts with hooks (lint-staged + husky or equivalent) so they can't be forgotten. Maintain `.gitignore` from day one — `node_modules/`, build output, `.env*`, keys — the first forgotten `.env` commit is one too many. Commit generated files only when the project expects them (lockfiles, migrations).

## Git as a debugging tool

`git bisect run <test-cmd>` mechanically finds the commit that broke something; `git blame` finds the context behind a line; `git log --grep` searches decision history. This is a payoff of atomic commits — bisect can't help when every commit changes twelve things.

## Verification

Each commit does one thing, has a why-message, passed tests before committing, contains no secrets, and mixes no formatting into behavior changes.
