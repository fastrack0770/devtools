---
name: observability-and-instrumentation
description: Instruments code so production behavior is visible and diagnosable. Use when adding logging, metrics, tracing, or alerting; when shipping a feature that runs in production; or when incidents can't be explained from available data. Not for diagnosing a live failure (debugging-and-error-recovery), profiling measured slowness (performance-optimization), or launch-day monitoring checklists (shipping-and-launch).
---

# Observability and Instrumentation

Code you can't observe is code you can't operate. Instrumentation is written alongside the feature, like tests — a feature shipped without telemetry turns its first bug report into archaeology instead of a query.

## Start from questions, not signals

Before instrumenting, write the 2–4 questions an on-call engineer will ask about this feature ("what fraction of payments succeed after retry?", "when one fails permanently, why?"). Every signal you add must answer one of them. If you can't name the questions, you'll log everything and learn nothing.

Then pick the right signal per question: **metrics** say *that* something is wrong (aggregate rate/latency, cheap, fixed cost per series), **traces** say *where* (per-request, sampled), **logs** say *why* (per-event detail).

## Structured logging

Log events, not prose: a stable event name plus machine-readable fields (`{event: 'payment_failed', provider, errorCode, attempt}`), never string interpolation — interpolated lines can't be queried, filtered, or alerted on.

- Levels mean something: `error` = invariant broken, someone may act; `warn` = degraded but handled; `info` = significant business event; `debug` = off in production.
- **Correlation IDs are mandatory.** Accept or generate a request ID at the boundary, attach it to every log line, span, and outbound call — without it interleaved logs can't be reassembled into one request's story.
- **Never log secrets, tokens, or unredacted PII** (hard rule shared with security-and-hardening — telemetry is a classic leak path). Allowlist fields; never dump whole request bodies.

## Metrics

**RED** on every endpoint and external dependency: Rate, Errors, Duration (as a histogram). **USE** for resources: Utilization, Saturation, Errors. Prefer the OpenTelemetry metrics API for vendor neutrality.

- **Cardinality is the failure mode.** Labels come from small fixed sets only — route template, status *class* (`5xx`, not `500`), provider name. User IDs, raw URLs, and error text as labels will melt the metrics backend; that detail belongs in logs and traces.
- **Percentiles always, averages never** — an average hides the 1% having a terrible time. Histograms, read p50/p95/p99.

## Tracing

OpenTelemetry with auto-instrumentation covers HTTP/gRPC/DB clients at near-zero code (import the SDK setup before anything else). Add manual spans only around meaningful internal units of work, with the attributes on-call will filter by. Propagate context across every async boundary — headers, queue metadata — or the trace dies at the gap. Sample low by default; keep 100% of errors if the backend supports tail sampling.

## Alerting

Alert on **symptoms users feel** (error rate > threshold, p99 latency, queue age), not causes (CPU %, pod restarts) — cause alerts fire when nothing is wrong and miss failures you didn't predict; symptom alerts fire exactly when users hurt, whatever the cause. For every alert:

1. Actionable — if the response is "ignore, it self-heals", delete it.
2. Linked to a runbook, even three lines: meaning, first query, escalation.
3. Threshold and duration justified by SLO or history, not guessed.
4. Two severities only — **page** (act now) and **ticket** (act this week); a third tier trains people to ignore all of them.

## Verify the telemetry itself

Instrumentation is code and can be wrong. Before done: force an error in staging and find it by requestId with structured fields intact; send traffic and confirm metric series with expected labels; follow one request end-to-end in the tracing UI with no broken spans; test-fire each new alert and confirm channel + runbook link. The end state: an induced staging failure is diagnosable from telemetry alone, without reading source.
