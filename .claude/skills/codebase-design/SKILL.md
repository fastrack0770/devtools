---
name: codebase-design
description: Designs deep modules with small interfaces at clean seams. Use when designing or improving a module's interface, deciding where a seam goes, deepening shallow modules, making code testable or agent-navigable, or when another skill needs deep-module vocabulary. Not for local readability cleanups (code-simplification) or REST/type contract conventions (api-and-interface-design).
---

# Codebase Design

Design deep modules: a lot of behaviour behind a small interface, placed at a clean seam and testable through that interface. Use this shared language wherever code is designed or restructured. The goal is leverage for callers and locality for maintainers.

## Glossary

Use these terms consistently; the avoid lists prevent overloaded substitutes.

**Module**: anything with an interface and an implementation. It may be a function, class, package, or tier-spanning slice. _Avoid_: unit, component, service.

**Interface**: everything a caller must know to use the module correctly: type signature, invariants, ordering constraints, error modes, required configuration, and performance characteristics. _Avoid_: API, signature (both are too narrow).

**Implementation**: what is inside a module, its body of code. It differs from an adapter: use adapter when the seam is the topic and implementation otherwise.

**Depth**: leverage at the interface: behaviour a caller or test can exercise per unit of interface learned. A deep module hides much behaviour behind a small interface; a shallow module's interface is nearly as complex as its implementation.

**Seam**: a place where behaviour can change without editing at that place; the location where a module's interface lives. Seam placement is separate from deciding what goes behind it. _Avoid_: boundary (overloaded by bounded contexts).

**Adapter**: a concrete thing satisfying an interface at a seam. It names the role a thing fills, not its substance.

**Leverage**: what callers get from depth: more capability per unit of interface learned. One implementation pays back across many call sites and tests.

**Locality**: what maintainers get from depth: change, bugs, knowledge, and verification concentrate in one place. Fix once, fixed everywhere.

## Deep and shallow modules

Deep module = small interface plus substantial hidden behaviour:

```text
+---------------------+
|   Small Interface   |
+---------------------+
|                     |
| Deep Implementation |
|                     |
+---------------------+
```

Shallow module = large interface plus thin implementation:

```text
+---------------------------------+
|        Large Interface          |
+---------------------------------+
|       Thin Implementation       |
+---------------------------------+
```

Reduce methods, simplify parameters, and hide complexity inside.

## Principles

- **Depth is a property of the interface, not the implementation.** Internals may contain small swappable parts and private seams without exposing them.
- **The deletion test.** If deleting a module makes complexity vanish, it was a pass-through. If complexity reappears across callers, it earned its keep.
- **The interface is the test surface.** Callers and tests cross the same seam. Wanting to test past it signals the module may have the wrong shape.
- **One adapter means a hypothetical seam; two adapters mean a real one.** Introduce a seam when behaviour actually varies there.

## Designing for testability

Accept dependencies rather than constructing them internally. Return results where possible rather than hiding outcomes in side effects. Keep methods and parameters few so both callers and tests have less setup and less interface to learn.

Internal seams may support implementation tests, but keep them private. Observable behaviour through the external interface remains the durable test surface.

## Relationships

- A **Module** has one **Interface**, presented to callers and tests.
- **Depth** belongs to a module and is measured against its interface.
- A **Seam** is where that interface lives.
- An **Adapter** sits at a seam and satisfies the interface.
- Depth produces **Leverage** for callers and **Locality** for maintainers.

## Rejected framings

- Depth as implementation-lines divided by interface-lines rewards padding. Judge leverage instead.
- Interface as only a language keyword or public method list omits the facts callers must know.
- Boundary is overloaded. Use seam or interface.

## Deeper work

Load `references/deepening.md` when restructuring a shallow cluster or classifying dependencies and test seams.

Load `references/design-it-twice.md` when the first plausible interface should be challenged with radically different alternatives.

## Verification

The interface is smaller than the behaviour it exposes; seam placement follows real variation; tests observe outcomes through the interface; dependencies and adapters are explicit; the design improves leverage and locality under the deletion test.
