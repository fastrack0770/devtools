---
name: ci-cd-and-automation
description: Automates CI/CD pipeline setup. Use when creating or modifying build/deploy pipelines, adding automated quality gates, or debugging CI failures. Not for running an existing pipeline, one-off local builds, or deploy decisions covered by shipping-and-launch.
---

# CI/CD and Automation

CI is the enforcement mechanism for every other practice: no change reaches main without passing the gates, consistently, on every change.

Two governing ideas:

- **Shift left.** A bug caught by lint costs minutes; the same bug in production costs hours. Order checks cheapest-first: static analysis → unit tests → build → integration → E2E.
- **Faster is safer.** Small batches and frequent releases reduce risk — a deploy with 3 changes debugs faster than one with 30, and a frequently exercised release process is a trusted one.

## Quality gates

Standard PR pipeline: lint → typecheck → unit tests → build → integration tests → (E2E for critical flows) → security audit → bundle-size check.

**Gates don't get skipped, they get fixed.** Lint failure → fix the code, not disable the rule. Flaky test → fix the flakiness, not re-run until green; a flaky test masks real bugs and erodes trust in the whole suite. Disabled tests in CI are a red flag, not a workaround.

## Wiring it up

Adapt to the project's platform; the shape matters more than the vendor:

- Run on every PR and push to main; failures block merge (branch protection, no force-push to main).
- Reproducible installs (`npm ci` / lockfile-strict equivalent), cached dependencies.
- Independent checks (lint / typecheck / test) run as parallel jobs.
- Integration tests get ephemeral services (e.g. a Postgres service container with health checks) and run migrations first.
- Even CI-only test credentials live in the secrets manager, never hardcoded — CI must have no production secrets at all.
- Upload failure artifacts (test reports, traces) so failures are diagnosable without re-running.

Environment layout: `.env.example` committed as template; real `.env` never committed; CI secrets in the platform's secrets store; production secrets in the deploy platform/vault.

## The feedback loop

CI's value with agents is the loop: on failure, feed the specific error back — lint errors get auto-fixed and committed; type errors get read and fixed at the reported location; test failures go through debugging-and-error-recovery; build errors usually mean config or dependency drift. Verify locally before pushing again.

## Beyond the PR pipeline

- **Preview deployments** per PR where the platform supports it — reviewers click, not imagine.
- **Feature flags** decouple deploy from release (rollout mechanics live in shipping-and-launch); every flag gets an owner and cleanup date at creation.
- **Automated dependency updates** (Dependabot/Renovate) on a weekly cadence with a bounded PR count.
- **Build cop:** when main breaks, one designated person fixes or reverts immediately — not whoever broke it, and not "someone eventually".

## When the pipeline gets slow

Apply in order of impact: cache dependencies → parallelize independent jobs → path-filter to skip unrelated work (docs-only PRs skip E2E) → shard slow suites across runners → move slowest tests off the critical path to a schedule → bigger runners last. A pipeline much beyond ~10 minutes changes developer behavior for the worse — treat that as a budget.

## Verification

All gates present and blocking; pipeline triggers on PR and main; secrets in the secrets manager; a rollback mechanism exists; failure output is actionable enough to feed straight back into a fix.
