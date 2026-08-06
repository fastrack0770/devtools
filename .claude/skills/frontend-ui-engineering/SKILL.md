---
name: frontend-ui-engineering
description: Builds production-quality UIs. Use when creating or modifying user-facing components, layouts, or client-side state, or when output must look designed rather than AI-generated. Not for backend endpoints, CLI output, or pure logic with no rendered interface.
---

# Frontend UI Engineering

Build interfaces that are accessible, performant, and visually polished — UI that reads as the work of a design-aware engineer, not a template. That means real design-system adherence, proper accessibility, and thoughtful interaction states.

## Avoid the AI aesthetic

Generated UI has recognizable tells. Use the project's actual design system instead of these defaults:

| AI default | Production quality |
|---|---|
| Purple/indigo palette, heavy gradients | The project's palette; flat or subtle per the design system |
| `rounded-2xl` everything, layered shadows | The design system's radius and elevation scale |
| Uniform card grids, generic hero sections | Layouts driven by content priority and scanning patterns |
| Oversized equal padding everywhere | The spacing scale, used to create hierarchy |
| Lorem-ipsum copy | Realistic content — it exposes wrapping and overflow problems |

## Component architecture

- **Composition over configuration** — `<Card><CardHeader>…` beats a `<Card title= headerVariant= bodyPadding=…>` prop explosion.
- **One responsibility per component**; split anything trying to be a page.
- **Separate data from presentation** — a container handles fetching/loading/error/empty, a presentational component renders. Every data-driven view handles all four states: loading (skeletons, not spinners, for content), error (with retry), empty (with a next action), success.
- **Colocate** component, tests, hooks, and types in the component's directory.

## State management

Choose the simplest level that works, in this order:

```
Local state (useState)           → Component-specific UI state
Lifted state                     → Shared between a few siblings
Context                          → Theme, auth, locale (read-heavy, write-rare)
URL state (searchParams)         → Filters, pagination, shareable UI state
Server state (React Query, SWR)  → Remote data with caching
Global store (Zustand, Redux)    → Complex client state shared app-wide
```

Prop drilling through components that don't use the props is the signal to restructure or reach for context.

## Design system discipline

- Spacing, radii, and type sizes come from the project's scale — never invented one-off values (`13px`, `2.3rem`).
- Semantic color tokens (`text-primary`, `bg-surface`), not raw hex.
- Type hierarchy is semantic: one `h1` per page, no skipped heading levels, no heading styles on non-headings.
- Contrast ≥ 4.5:1 for normal text (3:1 large); never color as the only carrier of meaning.

## Accessibility

WCAG 2.1 AA is the floor, not a stretch goal: every interactive element keyboard-reachable (prefer native elements — `<button>`, not a click-handler `<div>`), labeled controls, managed focus on dialogs and dynamic content, `role="status"`/live regions for async updates. Load `references/accessibility-checklist.md` for the full requirements, code patterns, and testing tools when building interactive components or auditing a page.

## Responsive and perceived performance

Mobile-first; verify at narrow (~320px), tablet, and desktop widths. Use optimistic updates where the mutation is very likely to succeed and easy to roll back.

## Verification

Render with a clean console; Tab through every flow; run an accessibility audit (axe-core or dev-tools equivalent); check the narrow-viewport layout; confirm loading/error/empty states exist. A screenshot at the target breakpoints is evidence; "looks fine on my screen" is not.
