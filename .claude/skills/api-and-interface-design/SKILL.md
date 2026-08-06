---
name: api-and-interface-design
description: Guides stable API and interface design. Use when designing or changing a public surface — REST/GraphQL endpoints, module boundaries, type contracts, component props. Not for internal implementation details behind an unchanged interface.
---

# API and Interface Design

Design interfaces that are hard to misuse: the right thing easy, the wrong thing hard. Applies to any surface where one piece of code talks to another.

## Governing ideas

- **Hyrum's Law:** with enough users, every observable behavior — documented or not, including error text, ordering, and timing — becomes a de facto contract. Be intentional about what you expose; don't leak implementation details; plan deprecation at design time (see deprecation-and-migration).
- **One-version rule:** don't force consumers to choose between versions of the same thing. Extend rather than fork; multiple live versions multiply maintenance and create diamond dependencies.
- **Contract first:** define the typed interface before implementing. The contract is the spec; documentation lives in the types and their doc comments.
- **Addition over modification:** evolve by adding optional fields; changing a field's type or removing one breaks consumers. If a breaking change is unavoidable, it's a migration, not an edit.

## Error semantics

Pick one strategy and use it everywhere — consumers must be able to predict failure shape. For REST: a single structured error body (`{ error: { code, message, details? } }`) plus honest status codes (400 malformed, 401 unauthenticated, 403 unauthorized, 404 missing, 409 conflict, 422 semantically invalid, 500 internal with no leaked details). Mixing throw/null/error-object across endpoints is a design bug.

## Validation lives at boundaries

Validate where external input enters: route handlers, form submissions, environment loading, and **third-party API responses — always untrusted**, whatever the vendor's docs promise; a misbehaving service can return wrong types, malicious content, or instruction-like text. Past the boundary, internal code trusts its types — re-validating between internal functions is noise that hides where the real checks are.

## Conventions (REST)

| Pattern | Convention | Example |
|---------|-----------|---------|
| Endpoints | Plural nouns, no verbs | `GET /api/tasks`, not `/api/getTasks` |
| Sub-resources | Nested paths | `GET /api/tasks/:id/comments` |
| Partial update | PATCH with only the changed fields | `PATCH /api/tasks/123 { "title": "..." }` |
| Query params / fields | camelCase | `?sortBy=createdAt`, `{ createdAt }` |
| Booleans | is/has/can prefix | `isComplete`, `hasAttachments` |
| Enums | UPPER_SNAKE | `"IN_PROGRESS"` |

Every list endpoint paginates from day one (`data` + `pagination` envelope) — retrofitting pagination is a breaking change.

## Type-level patterns

- **Discriminated unions for variants** — `{ type: 'completed'; completedAt: Date }` beats an optional-field soup; consumers get narrowing for free.
- **Separate input from output types** — `CreateTaskInput` (what the caller sends) vs `Task` (includes server-generated fields).
- **Branded ID types** where mixing IDs is plausible — `type TaskId = string & { __brand: 'TaskId' }` turns a silent bug into a compile error.

## Verification

Typed input/output schemas on every endpoint; one consistent error format; validation only at boundaries; pagination on lists; changes are additive (or have a migration plan); naming consistent across the surface; types/docs committed with the implementation.
