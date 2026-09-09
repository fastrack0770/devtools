# CONTEXT.md Format

## Structure

```md
# {Context Name}

{One or two sentences describing the context and why it exists.}

## Language

**Order**:
{A one- or two-sentence definition of the term.}
_Avoid_: Purchase, transaction
```

## Rules

- Pick one canonical term and put competing words under `_Avoid_`.
- Keep definitions to one or two sentences. Define what the concept is, not its implementation.
- Include only concepts specific to this domain. General programming concepts do not belong.
- Add subheadings when natural clusters emerge; otherwise retain a flat list.

## Single and multiple contexts

Most repositories use one root `CONTEXT.md`.

For multiple bounded contexts, keep a root `CONTEXT-MAP.md` that links each context's local `CONTEXT.md` and records their relationships:

```md
# Context Map

## Contexts

- [Ordering](./src/ordering/CONTEXT.md): receives and tracks orders
- [Billing](./src/billing/CONTEXT.md): generates invoices

## Relationships

- **Ordering -> Billing**: Ordering emits `OrderPlaced`; Billing consumes it.
```

If `CONTEXT-MAP.md` exists, use it. If only root `CONTEXT.md` exists, use the single context. If neither exists, create root `CONTEXT.md` lazily when the first term is resolved. Ask when a multi-context term cannot be placed confidently.
