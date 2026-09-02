---
name: writing-for-agents
description: Writes predictable documents for agents with sharp pointers and progressive disclosure. Use when creating or editing a skill, editing CLAUDE.md, AGENTS.md, or another rules file, or writing a document an agent reaches through a pointer. Not for human-facing documentation (documentation-and-adrs) or deciding what context a task loads (context-engineering).
---

# Writing for Agents

Write any document an agent consumes so repeated runs follow the same process, even when outputs differ. Skills, rules files, and pointed-at documents share the same levers. Protect attention with sharp pointers, hierarchy, completion criteria, and pruning.

## Context pointers

A **context pointer** names out-of-context material and the condition for loading it. A skill description and an `AGENTS.md` link are the same kind of object: wording decides whether the target is reached.

- Front-load the **leading word** that should trigger retrieval.
- Give each genuine branch one trigger. Collapse synonyms for the same branch.
- State what the target is and when to load it; remove identity already carried by the body.
- Sharpen a weak pointer before inlining its target.

## The two loads

**Context load** is always-present material consuming window and attention on every turn. **Cognitive load** is what humans spend remembering which documents exist and when to invoke them. Spend cognitive load where human judgment matters; use pointers where autonomous discovery matters.

Material behind a pointer avoids most context load at the cost of the pointer. Material without a pointer relies entirely on the human as index.

## Information hierarchy

Rank material by immediacy:

1. In-file steps: ordered actions the agent performs.
2. In-file reference: definitions and rules consulted while acting.
3. Disclosed reference: branch-specific detail behind an explicit pointer.

**Progressive disclosure** moves branch-specific reference down the hierarchy so primary steps remain visible. Inline what every branch needs; disclose what only one branch needs.

**Co-location** keeps a concept's definition, rules, and caveats together under one heading. **Sprawl** is excess length even when lines are unique; cure it by disclosing reference or splitting real branches and sequences.

## Steps and completion criteria

Every step needs a completion criterion with:

- **Clarity**: the agent can distinguish done from unfinished. Sharpen fuzzy bounds before changing structure.
- **Demand**: the criterion requires enough legwork, such as accounting for every modified model rather than merely producing a list.

Visible post-completion steps can pull attention forward and cause **premature completion**. If a clear criterion still fails in practice, split at a real context boundary so later steps are not loaded. An inline call does not clear context.

## When to split

Split by sequence when later steps repeatedly rush a demanding earlier step. Split by branch when each path needs substantially different reference. When the document is a skill, load `references/skill-mechanics.md` to decide invocation and whether to split or route skills.

Each split spends context or cognitive load, so require a concrete retrieval or execution benefit.

## Leading words and negation

A **leading word** is a compact, pretrained concept that anchors behavior: seam, tracer bullet, frontier, tight loop. Repeat the token rather than its definition so it recruits stable prior knowledge without duplicated prose.

Refactor repeated explanations into a strong leading word. Prefer existing vocabulary; coined terms must repay their definition cost.

Negation activates the forbidden behavior. State the positive target instead. Keep prohibitions only for hard guardrails, and pair each with the behavior to perform.

## Pruning

- Keep every meaning in one **single source of truth**. Repeating a leading word is useful; duplicating its definition is not.
- Treat the environment as a source of truth. Commands, config, and layouts are cheap lookups; document only costly context, reasons, conventions, and gotchas.
- Test every line for **relevance** to the document's job. Remove stale **sediment** rather than preserving it from caution.
- Hunt **no-ops**: instructions that do not change model behavior. Delete the whole sentence or choose a stronger leading word.

## House rules for this collection

- Frontmatter uses `name:` equal to the directory and a one-paragraph description: `<Verb phrase describing what it does>. Use when <triggers>. Not for <non-triggers>.` Keep it under about 600 characters.
- A model-invoked skill uses that model-facing description. A user-invoked skill adds `disable-model-invocation: true` and uses a short human-facing description without trigger lists.
- The body starts with `# Title` and a two-to-four sentence introduction stating the job and defining constraint.
- Step-shaped skills give every step a `Done when:` completion criterion. Reference-shaped skills use flat rules.
- End with `## Verification` stating what must be true before completion.
- Aim for 60-130 lines. The linter `scripts/check_skills.py` warns above 150 and fails above 400.
- Put examples, long lists, and formats in `references/` and state exactly when each reference should be loaded.
- Operative dependencies use exactly `Call the Skill tool with "X"`.
- Prefer positive phrasing; reserve prohibitions for hard guardrails and pair them with the positive target.
- Reject boilerplate sections named Common Rationalizations, Red Flags, or Anti-Patterns; choose a specific heading such as Failure modes.

## Verification

Pointers front-load distinct triggers; steps have clear and demanding completion criteria; branch-specific detail is disclosed; related material is co-located; each meaning has one source of truth; environment lookups are not cached without reason; stale, irrelevant, and no-op prose is removed; applicable house rules and the skill linter pass.
