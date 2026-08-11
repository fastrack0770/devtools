---
name: source-driven-development
description: Grounds framework-specific implementation decisions in official documentation. Use when writing framework/library code where the current version's patterns matter (forms, routing, data fetching, auth), or when the user asks for verified, documented, source-cited code. Not for version-independent logic, mechanical edits, or when the user explicitly chose speed over verification.
---

# Source-Driven Development

Training data goes stale: APIs deprecate, best practices move. Framework-specific decisions get verified against official documentation and cited, so the user can check every pattern — instead of discovering a hallucinated signature an hour into debugging.

## The process: detect → fetch → implement → cite

**1. Detect the stack and exact versions** from the dependency file (`package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `Gemfile`, `composer.json`) and state what you found. Version determines which patterns are correct — if it's ambiguous, ask, don't guess.

**2. Fetch the specific documentation page** for the feature at hand — `react.dev/reference/react/useActionState`, not the homepage; the versioned Django auth topic page, not a search for "best practices".

Source hierarchy: official docs → official blog/changelog → web standards (MDN, spec) → compatibility tables (caniuse, node.green). **Never cite as primary:** Stack Overflow, tutorials/blog posts however popular, AI-generated summaries, or your own training data — verifying that last one is the entire point. When official sources contradict each other (migration guide vs API reference), surface the discrepancy and verify against the detected version.

**3. Implement the documented pattern.** Use signatures from the docs, not memory; prefer what current docs recommend; never use what they deprecate. When docs conflict with existing project code, surface it as an explicit choice — modern pattern vs codebase consistency — and let the user pick; don't silently decide.

**4. Cite.** Every framework-specific pattern gets a full URL (deep links with anchors survive doc restructuring best), in a code comment at the usage site and/or in conversation, quoting the relevant passage for non-obvious decisions. Include compatibility data when recommending platform features.

When you can't find documentation for a pattern:

```
UNVERIFIED: no official documentation found for this pattern.
Based on training data; may be outdated. Verify before production use.
```

Honest UNVERIFIED beats hedged confidence — a disclaimer sprinkled over unverified code helps no one.

## Why the discipline pays

Simple tasks with wrong patterns become templates: one deprecated form handler gets copied into ten components before anyone notices the modern approach exists. One page fetch is cheaper than that.

## Verification

Versions read from the dependency file; official docs fetched for each framework-specific pattern; no deprecated APIs (checked against migration guides); non-trivial decisions carry full-URL citations; docs-vs-codebase conflicts surfaced; everything unverifiable explicitly flagged.
