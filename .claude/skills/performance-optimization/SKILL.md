---
name: performance-optimization
description: Optimizes application performance. Use when a measured or reported slowness exists — failing Core Web Vitals, slow endpoints, regressions after a change — or when the spec sets explicit performance budgets. Not a default pass for every feature; don't invoke without evidence of a problem or a stated requirement.
---

# Performance Optimization

Measure before optimizing. Performance work without measurement is guessing, and guessing produces premature optimization that adds complexity without improving what matters.

## Workflow

1. **Measure** — establish a baseline with real numbers.
2. **Identify** — find the actual bottleneck, not the assumed one.
3. **Fix** — address that specific bottleneck.
4. **Verify** — measure again; the numbers must move.
5. **Guard** — add a test, budget, or monitor so it doesn't regress silently.

Skipping step 1 invalidates everything after it: if you didn't measure, you don't know.

## Measuring

Use both kinds of measurement when user experience is the target:

- **Synthetic** (Lighthouse, DevTools Performance trace): reproducible, good for CI regression gates and isolating causes.
- **RUM** (web-vitals library, CrUX): real users, real conditions — the only way to confirm a fix actually helped.

Let the symptom pick the first measurement:

- Slow first load → bundle size, TTFB in the network waterfall, render-blocking resources.
- Sluggish interaction → main-thread long tasks (>50 ms), re-renders, layout thrashing.
- Slow after navigation → API response times, request waterfalls, N+1 fetches.
- Slow backend → query log with timings for one endpoint; connection pool/CPU/memory if everything is slow; lock contention, GC, external dependencies if intermittent.

Core Web Vitals "good" thresholds (external standard, worth knowing): LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1.

## High-frequency culprits

Check these before anything exotic — they account for most real-world slowness:

- **N+1 queries** — one query per row instead of a join/include.
- **Unbounded fetching** — list endpoints without pagination or limits.
- **Unoptimized images** — missing dimensions (CLS), no lazy loading, no responsive sizes, oversized formats.
- **Oversized bundles** — no route-level code splitting, heavy rarely-used features loaded eagerly.
- **Missing caching** — recomputing or refetching frequently-read, rarely-changed data; no HTTP cache headers on static assets.
- **Render churn (React)** — unstable object/function props, missing memoization on genuinely expensive work. The inverse is also a smell: `memo`/`useMemo` sprinkled everywhere without measurement.

## Budgets

Agree on budgets with the team and enforce them in CI (bundle-size check, Lighthouse CI) — a budget that isn't enforced is a wish. Concrete numbers belong to the project, not this skill; the reference has a worked example set.

## References

Load `references/performance-checklist.md` when fixing a specific culprit: code patterns for N+1, pagination, responsive images, React re-renders, code splitting, and caching; an example budget with CI enforcement commands; and the pre-merge performance checklist.

## Verification

Before-and-after numbers for the specific bottleneck, tests still pass, and a regression guard exists. An "optimization" without a measured improvement is a complexity increase.
