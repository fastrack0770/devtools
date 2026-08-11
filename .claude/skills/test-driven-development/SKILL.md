---
name: test-driven-development
description: Drives development with tests. Use when implementing new logic, fixing a bug, or changing behavior that an automated test can verify. Not for config-only changes, documentation, pure styling, or throwaway exploration — but add tests before a prototype becomes permanent.
---

# Test-Driven Development

Write a failing test before the code that makes it pass. For bug fixes, reproduce the bug with a test before attempting a fix. Tests are proof — "seems right" is not done. A codebase with good tests is an agent's superpower; one without is a liability.

## The cycle

**RED** — write a test that fails. A test that passes immediately proves nothing.
**GREEN** — write the minimum code to pass. Don't over-engineer.
**REFACTOR** — clean up with tests green; re-run after each step.

## Bug fixes: the Prove-It pattern

Never start with the fix. Write the reproduction test first, watch it fail (bug confirmed), implement the fix, watch it pass (fix proven), then run the full suite for regressions. A bug fix without a reproduction test can silently regress.

## Choosing the test level

- Pure logic, no I/O → **unit test** (milliseconds; the bulk of the suite, ~80%).
- Crosses a boundary — API, database, filesystem → **integration test** (~15%).
- Critical user flow end-to-end → **E2E** (~5%; expensive, reserve for paths that must not break).

If a change breaks your code and no test catches it, that's a gap in *your* tests, not the refactor's fault — put a test on anything you care about.

## What makes a test good

- **Assert state, not interactions.** Test what the function returns/changes, not which internal methods it called — interaction tests shatter on refactor.
- **DAMP over DRY.** Each test reads as a self-contained story; duplication in tests is fine when it aids comprehension.
- **Prefer real implementations** over doubles: real > fake > stub > mock. Mock only what's slow, non-deterministic, or side-effectful (external APIs, email). Over-mocking produces tests that pass while production breaks.
- **One behavior per test, named as a specification** — `it('throws NotFoundError for non-existent task')`, not `it('handles errors')`.
- **Isolated and deterministic** — no ordering dependencies, no timing flake; each test owns its setup and teardown.

## Browser code

Unit tests aren't enough for anything that runs in a browser — combine with runtime verification (DOM, console, network, screenshots) via the browser-testing-with-devtools skill.

## References

Load `references/testing-patterns.md` for concrete code examples: RED/GREEN walkthrough, reproduction-test example, state-vs-interaction and DAMP comparisons, Arrange-Act-Assert, naming, and the anti-pattern table.

## Verification

Every new behavior has a test; the suite passes; bug fixes include a reproduction test that failed before the fix; nothing skipped or disabled. Run the test command after changes that could affect the result — but don't re-run an unchanged suite for reassurance; a second identical run adds no information.
