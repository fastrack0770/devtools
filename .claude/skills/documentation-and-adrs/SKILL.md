---
name: documentation-and-adrs
description: Records decisions and documentation. Use when making an architectural decision, changing a public API, shipping a user-visible feature, or capturing context future engineers and agents will need. Not for restating what code already says, or documenting throwaway prototypes.
---

# Documentation and ADRs

Document the *why*, not the *what*. Code shows what was built; the valuable documentation captures context, constraints, rejected alternatives, and trade-offs — the things future humans and agents cannot recover from the code.

## Architecture Decision Records

The highest-value documentation you can write. Write one for any decision that would be expensive to reverse: framework/major dependency choice, data model or schema design, auth strategy, API architecture, build/hosting/infrastructure.

Keep them in `docs/decisions/`, numbered sequentially, with this shape:

```markdown
# ADR-NNN: <decision as a sentence>

## Status        Proposed | Accepted | Superseded by ADR-XXX | Deprecated
## Date
## Context       — the requirements and constraints that forced a choice
## Decision      — what was chosen, in one or two sentences
## Alternatives Considered — each with pros, cons, and why rejected
## Consequences  — what this commits us to, good and bad
```

The **Alternatives Considered** section is the point — a decision without rejected alternatives is a description, not a record. Never delete old ADRs; when a decision changes, a new ADR supersedes the old one, preserving the historical context.

## Comments

Comment the *why*; delete comments that restate the code:

- Keep: intent the code can't express — `// sliding window, not fixed schedule, to prevent burst attacks at window edges`; known gotchas at the point of danger (`must run before first render — post-hydration causes FOUC; see ADR-003`).
- Delete: `// increment counter` above `counter += 1`; commented-out code (git has history); stale TODOs — either do it now or file it.

Why-comments stay true as code evolves; what-comments rot — that's the whole rule.

## API documentation

Public surfaces get documented at the source of truth: doc comments on the typed interface (params, returns, thrown errors, one example) for libraries; OpenAPI/schema files for REST. Docs that live next to the types get updated; docs that live in a wiki don't.

## Project-level docs

- **README:** what the project does, quick start that actually works, command table, brief architecture overview linking to ADRs. If a newcomer can't run the project from the README, the README has failed.
- **Changelog:** per release — Added / Fixed / Changed, each entry linked to its PR or issue.
- **Agent context:** CLAUDE.md and rules files are documentation too — keep them current, and keep them lean (see context-engineering). ADRs prevent agents from re-litigating settled decisions; inline gotchas prevent them from falling into known traps.

## Verification

Significant decisions have ADRs with alternatives; public APIs are documented at the type level; README quick-start verified to work; no commented-out code or stale TODOs left; rules files reflect current reality.
