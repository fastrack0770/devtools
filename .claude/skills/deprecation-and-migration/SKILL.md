---
name: deprecation-and-migration
description: Manages deprecation and migration. Use when removing or replacing a system, API, or feature that has consumers, when consolidating duplicate implementations, or when deciding whether to maintain or sunset legacy code. Not for deleting freshly written or provably unused code — that's ordinary cleanup.
---

# Deprecation and Migration

Code is a liability, not an asset — its value is the functionality, and every line carries maintenance cost (patches, dependency updates, onboarding overhead). Deprecation removes code that no longer earns its keep; migration moves its users safely. Most organizations build well and remove badly; this skill is about the removal half.

## Governing ideas

- **Hyrum's Law makes removal hard:** with enough users, every observable behavior — bugs and quirks included — is depended on. So deprecation requires *active migration*, not an announcement; users can't "just switch" off behaviors the replacement doesn't replicate.
- **Plan removal at design time.** When building something new, ask "how would we remove this in 3 years?" — clean interfaces, flags, and small surface area make future deprecation feasible.
- **The Churn Rule:** if you own the infrastructure being deprecated, *you* migrate your users (or ship backward-compatible updates needing no migration). Announcing a deadline and walking away is not deprecation.

## Deciding to deprecate

1. Does it still provide unique value? If yes — maintain, stop here.
2. How many consumers depend on it? Quantify before planning.
3. Does a replacement exist? If no, build it first — never deprecate into a void.
4. What's each consumer's migration cost? Trivially automatable → just do it; high-effort manual → weigh against maintenance cost.
5. What does *not* deprecating cost over 2–3 years? Security exposure, engineer time, complexity tax. That comparison, not sentiment, makes the call.

**Advisory vs compulsory:** default to advisory (warnings, docs, own-timeline migration). Go compulsory — hard removal date — only when security risk or unsustainable maintenance justifies forcing it, and then tooling, docs, and support are mandatory, not optional.

## The process

1. **Build the replacement** — covering all critical use cases, documented, proven in production. "Theoretically better" doesn't count.
2. **Announce and document** — status, replacement, removal date (or "advisory"), reason, and a concrete migration guide with real steps and a verification command.
3. **Migrate incrementally** — one consumer at a time: find its touchpoints, switch to the replacement, verify behavior matches, remove old references, confirm no regressions.
4. **Remove** — only after metrics/logs/dependency analysis show zero active usage: delete the code *and* its tests, docs, config, and the deprecation notices themselves. Removing code is an achievement; treat it like one.

## Migration patterns

- **Strangler:** run both systems, shift traffic 0% → canary → 50% → 100% → remove. Reversible at every step.
- **Adapter:** old interface delegating to the new implementation — consumers migrate on their schedule while the backend is already new.
- **Flag-per-consumer:** a feature flag switches consumers individually, giving instant rollback per consumer.

## Zombie code

Code nobody owns but everybody depends on: no commits in months yet active consumers, failing tests nobody fixes, vulnerable dependencies nobody bumps. It cannot stay in limbo — either assign an owner and maintain it properly, or deprecate it with a concrete plan. Watch for the inverse smell too: new features landing in a system already marked deprecated means investment is flowing the wrong way.

## Verification

Replacement production-proven; migration guide exists; zero active consumers confirmed by data (not assumption) before removal; old code, tests, docs, config, and notices fully gone; no dangling references in the codebase.
