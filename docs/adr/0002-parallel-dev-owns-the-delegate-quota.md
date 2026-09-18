# 0002: Parallel-dev owns the delegate quota

## Context
Concurrency capacity and safe partitioning policy evolve together, while duplicating a number in global rules creates conflicting authorities.

## Decision
Keep the numeric delegate quota and its resolution order only in `parallel-dev`. If that skill cannot load, fail closed: allow no concurrent delegates and no delegated file changes, while permitting one sequential read-only delegate.

## Why
One authority prevents stale limits; the fallback preserves safe review and lookup without guessing at a missing policy.
