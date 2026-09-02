# 0001: Codex is a delegate

## Context
Codex sessions can inspect a repository, make decisions, and in write mode change code just like Agent tool subagents.

## Decision
Count every Codex session as a delegate and launch it through `parallel-dev`'s `scripts/run_codex.sh`; write mode additionally requires the validated partitioning plan.

## Why
A common accounting and launch path keeps concurrency limits, read-only enforcement, worktree isolation, and ownership boundaries consistent across model runtimes.
