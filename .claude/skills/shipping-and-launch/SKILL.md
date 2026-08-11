---
name: shipping-and-launch
description: Prepares production launches. Use when deploying to production, planning a staged rollout, or defining rollback strategy and launch monitoring. Not for routine CI runs, staging-only deploys, or changes already covered by an active rollout plan.
---

# Shipping and Launch

Deploy safely: every launch reversible, observable, and incremental. "It worked in staging" is a hypothesis; production is the test.

## Hard rules

- **No deploy without a rollback plan** written before the deploy: trigger conditions, exact steps, expected time-to-rollback, and database considerations (does each migration have a down path; what happens to data the new feature wrote?).
- **Someone watches the first hour.** Health check, error dashboard, latency, one manual pass of the critical flow, logs flowing.
- **Decouple deploy from release** where the platform allows: ship dark behind a feature flag, then enable gradually.

## Staged rollout

```
1. Staging          → full suite + manual smoke test of critical flows
2. Production, OFF  → verify deploy (health check), no new errors
3. Team/internal ON → 24h monitoring window
4. Canary ~5%       → compare canary vs baseline, 24–48h
5. 25% → 50% → 100% → same checks each step, reversible at any point
6. Cleanup          → remove the flag and dead path after full rollout
```

Advance/hold/rollback thresholds (project defaults — tighten per SLA):

| Metric | Advance | Hold & investigate | Roll back |
|--------|---------|--------------------|-----------|
| Error rate | within 10% of baseline | 10–100% above | >2× baseline |
| P95 latency | within 20% of baseline | 20–50% above | >50% above |
| Client JS errors | no new types | new, <0.1% of sessions | new, >0.1% of sessions |
| Business metrics | neutral/positive | decline <5% | decline >5% |

Roll back immediately on data-integrity issues or a discovered security vulnerability, regardless of the table.

## Feature flag discipline

Every flag has an owner and an expiration; clean up within ~2 weeks of full rollout; never nest flags; CI tests both states. A stale flag is dead code with a live blast radius.

## Pre-launch checklist

Confirm each area, pulling detail from the owning skill when needed:

- **Quality:** tests/build/lint/types green; change reviewed; error handling covers expected failures; no leftover debug output.
- **Security:** walk `.claude/skills/security-and-hardening/references/security-checklist.md` for the surfaces this release touches.
- **Performance:** `.claude/skills/performance-optimization/references/performance-checklist.md` — vitals, budgets, N+1s.
- **Accessibility (user-facing UI):** `.claude/skills/frontend-ui-engineering/references/accessibility-checklist.md`.
- **Infrastructure:** env vars set, migrations ready, DNS/SSL/CDN configured, health endpoint live, logging and error reporting wired (see observability-and-instrumentation for what to instrument).
- **Docs:** README/setup, API docs, changelog, ADRs for decisions made along the way.

## Monitoring the launch

Watch three layers: application (error rate, p50/p95/p99 latency, volume, key business metrics), infrastructure (CPU/memory, connection pools, disk, queues), client (Core Web Vitals, JS errors, client-observed API failures). If a dashboard for these doesn't exist, creating it is part of the launch, not a follow-up.

## Verification

Before: checklist green, flag configured, rollback plan written, dashboards ready, team notified. After: health 200, error rate and latency at baseline, critical flow manually verified, logs readable, rollback mechanism confirmed workable.
