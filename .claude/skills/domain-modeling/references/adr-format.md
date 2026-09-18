# ADR Format

ADRs live in the applicable `docs/adr/` and use sequential names such as `0001-event-sourced-orders.md`. Scan the directory for the highest number and increment it. Create the directory lazily.

## Short format

```md
# {Short title of the decision}

{One to three sentences stating the context, decision, and reason.}
```

One paragraph is a valid ADR. The value is recording the decision and why it won, not filling a template.

Optional sections belong only when useful:

- **Status**: `proposed`, `accepted`, `deprecated`, or `superseded by ADR-NNNN`.
- **Considered Options**: rejected alternatives worth remembering.
- **Consequences**: non-obvious downstream effects.

## Qualification

An ADR must be hard to reverse, surprising without context, and the result of a real trade-off. Typical qualifiers include architectural shape, integration between contexts, technology choices with meaningful lock-in, ownership or scope boundaries, and deliberate deviations from the obvious approach.

Easy-to-reverse, unsurprising, or inevitable choices remain in their natural source of truth. Ordinary library selection and implementation detail usually do not qualify.
