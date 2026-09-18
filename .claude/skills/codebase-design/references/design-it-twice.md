# Design It Twice

Use this process to explore alternative interfaces for a chosen module. The first plausible design is unlikely to be the strongest.

## 1. Frame the problem

Write a concise explanation covering:

- constraints every interface must satisfy;
- dependency categories and likely seam locations;
- what behaviour belongs behind the seam;
- a rough code sketch that grounds the constraints without proposing a winner.

## 2. Produce alternatives

Produce three or four radically different designs yourself, sequentially. When the user explicitly wants delegation, `Call the Skill tool with "parallel-dev"` and stay inside its quota.

Give each design a distinct constraint:

1. Minimize the interface to one to three entry points and maximize leverage.
2. Maximize flexibility across known use cases and extensions.
3. Optimize for the common caller so the default case is trivial.
4. When relevant, organize dependencies around ports and adapters.

For every design provide:

- the full interface, including types, invariants, ordering, and errors;
- a caller usage example;
- behaviour hidden behind the seam;
- dependency and adapter strategy;
- trade-offs, including where leverage is high or thin.

Use both the codebase-design vocabulary and the project's `CONTEXT.md` vocabulary.

## 3. Compare and recommend

Present each design separately, then compare depth, locality, and seam placement. Recommend the strongest design and explain why. Propose a hybrid only when its combined interface remains coherent and smaller than the behaviour it exposes.
