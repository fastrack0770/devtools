---
name: documentation-and-adrs
description: Records decisions and documentation. Use when making an architectural decision, changing a public API, shipping a user-visible feature, or capturing context future engineers and agents will need. Not for restating what code already says, or documenting throwaway prototypes.
---

# Documentation and ADRs

Document the *why*, not the *what*. Code shows what was built; the valuable documentation captures context, constraints, rejected alternatives, and trade-offs — the things future humans and agents cannot recover from the code.

## Architecture Decision Records

Write an ADR only when all three gates hold: the decision is hard to reverse, surprising without context, and the result of a real trade-off.

Keep ADRs in `docs/adr/`, numbered sequentially. A title plus one to three sentences covering context, decision, and why is a complete ADR:

```markdown
# ADR-NNN: <decision as a sentence>

<Context, decision, and why in one to three sentences.>

## Status (optional)
## Alternatives Considered (optional)
## Consequences (optional)
```

Use optional sections only when they add value. **Alternatives Considered** remains strongly recommended for technology choices. Never delete old ADRs; when a decision changes, a new numbered ADR supersedes the old one and preserves the historical context.

## Project glossary

A project's ubiquitous language lives in root `CONTEXT.md` as a glossary only, without implementation detail. Changing that language belongs to the domain-modeling skill: Call the Skill tool with "domain-modeling" when a term is fuzzy, overloaded, or new.

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

Decisions meeting all three gates have numbered ADRs, with alternatives recorded for technology choices; public APIs are documented at the type level; README quick-start verified to work; no commented-out code or stale TODOs left; rules files reflect current reality.
